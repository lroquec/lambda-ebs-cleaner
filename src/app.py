"""
AWS Lambda function for cleaning up unused EBS volumes and snapshots.
Deletes volumes that are not attached and older than 7 days,
as well as snapshots that are either orphaned or from unused volumes.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Set, Dict, List

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class EBSCleaner:
    """
    Class to manage the cleanup of EBS volumes and snapshots.
    Handles the identification and deletion of unused resources.
    """

    def __init__(self):
        self.ec2 = boto3.client('ec2')
        self.retention_days = 7

    def get_active_instance_ids(self) -> Set[str]:
        """
        Retrieve all running EC2 instance IDs.

        Returns:
            Set[str]: Set of active instance IDs
        """
        active_instances = set()
        paginator = self.ec2.get_paginator('describe_instances')

        try:
            for page in paginator.paginate(Filters=[{
                'Name': 'instance-state-name',
                'Values': ['running']
            }]):
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        active_instances.add(instance['InstanceId'])

            logger.info('Found %d active instances', len(active_instances))
            return active_instances
        except ClientError as err:
            logger.error('Error getting active instances: %s', str(err))
            raise

    def get_volumes_to_delete(self) -> List[Dict]:
        """
        Identify volumes that are not in use and older than retention period.

        Returns:
            List[Dict]: List of volumes to delete with their metadata
        """
        volumes_to_delete = []
        paginator = self.ec2.get_paginator('describe_volumes')
        retention_date = datetime.now(timezone.utc) - timedelta(
            days=self.retention_days
        )

        try:
            for page in paginator.paginate(Filters=[{
                'Name': 'status',
                'Values': ['available']  # Only get detached volumes
            }]):
                for volume in page['Volumes']:
                    # Check if volume is older than retention period
                    if volume['CreateTime'] < retention_date:
                        volumes_to_delete.append({
                            'VolumeId': volume['VolumeId'],
                            'Size': volume['Size'],
                            'Age': (datetime.now(timezone.utc) -
                                  volume['CreateTime']).days
                        })

            logger.info('Found %d unused volumes to delete', len(volumes_to_delete))
            return volumes_to_delete
        except ClientError as err:
            logger.error('Error getting volumes: %s', str(err))
            raise

    def get_snapshots_to_delete(self) -> List[Dict]:
        """
        Identify snapshots that are orphaned (no volume) or from unused volumes.

        Returns:
            List[Dict]: List of snapshots to delete with their metadata
        """
        snapshots_to_delete = []
        paginator = self.ec2.get_paginator('describe_snapshots')
        retention_date = datetime.now(timezone.utc) - timedelta(
            days=self.retention_days
        )

        try:
            for page in paginator.paginate(OwnerIds=['self']):
                for snapshot in page['Snapshots']:
                    if snapshot['StartTime'] < retention_date:
                        if self._should_delete_snapshot(snapshot):
                            snapshots_to_delete.append({
                                'SnapshotId': snapshot['SnapshotId'],
                                'VolumeId': snapshot.get('VolumeId'),
                                'Age': (datetime.now(timezone.utc) -
                                      snapshot['StartTime']).days,
                                'Description': snapshot.get(
                                    'Description',
                                    'No description'
                                )
                            })

            logger.info('Found %d snapshots to delete', len(snapshots_to_delete))
            return snapshots_to_delete
        except ClientError as err:
            logger.error('Error getting snapshots: %s', str(err))
            raise

    def _should_delete_snapshot(self, snapshot: Dict) -> bool:
        """
        Determine if a snapshot should be deleted based on various criteria.

        Args:
            snapshot (Dict): Snapshot metadata

        Returns:
            bool: True if snapshot should be deleted
        """
        volume_id = snapshot.get('VolumeId')

        if not volume_id:
            logger.info('Snapshot %s has no volume ID', snapshot['SnapshotId'])
            return True

        try:
            volume_response = self.ec2.describe_volumes(VolumeIds=[volume_id])
            return volume_response['Volumes'][0]['State'] == 'available'
        except ClientError as err:
            if err.response['Error']['Code'] == 'InvalidVolume.NotFound':
                logger.info(
                    'Volume %s not found for snapshot %s',
                    volume_id,
                    snapshot['SnapshotId']
                )
                return True
            raise

    def delete_volumes(self, volumes: List[Dict]) -> None:
        """
        Delete the identified volumes.

        Args:
            volumes (List[Dict]): List of volumes to delete
        """
        for volume in volumes:
            try:
                self.ec2.delete_volume(VolumeId=volume['VolumeId'])
                logger.info(
                    'Deleted volume %s, Size: %sGB, Age: %s days',
                    volume['VolumeId'],
                    volume['Size'],
                    volume['Age']
                )
            except ClientError as err:
                logger.error(
                    'Error deleting volume %s: %s',
                    volume['VolumeId'],
                    str(err)
                )

    def delete_snapshots(self, snapshots: List[Dict]) -> None:
        """
        Delete the identified snapshots.

        Args:
            snapshots (List[Dict]): List of snapshots to delete
        """
        for snapshot in snapshots:
            try:
                self.ec2.delete_snapshot(SnapshotId=snapshot['SnapshotId'])
                logger.info(
                    'Deleted snapshot %s, Age: %s days, Description: %s',
                    snapshot['SnapshotId'],
                    snapshot['Age'],
                    snapshot['Description']
                )
            except ClientError as err:
                if err.response['Error']['Code'] == 'InvalidSnapshot.InUse':
                    logger.warning(
                        'Snapshot %s is in use, skipping deletion',
                        snapshot['SnapshotId']
                    )
                else:
                    logger.error(
                        'Error deleting snapshot %s: %s',
                        snapshot['SnapshotId'],
                        str(err)
                    )


def lambda_handler(event: Dict, context: Dict) -> Dict:
    """
    Main Lambda handler for EBS volume and snapshot cleanup.

    Args:
        event (Dict): Lambda event data
        context (Dict): Lambda context

    Returns:
        Dict: Execution summary
    """
    try:
        cleaner = EBSCleaner()

        # Clean up unused volumes
        volumes_to_delete = cleaner.get_volumes_to_delete()
        cleaner.delete_volumes(volumes_to_delete)

        # Clean up orphaned snapshots
        snapshots_to_delete = cleaner.get_snapshots_to_delete()
        cleaner.delete_snapshots(snapshots_to_delete)

        return {
            'statusCode': 200,
            'body': f'Successfully processed {len(volumes_to_delete)} volumes and {len(snapshots_to_delete)} snapshots'
        }
    except Exception as err:
        logger.error('Error in lambda execution: %s', str(err))
        raise