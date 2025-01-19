import boto3
from botocore.exceptions import ClientError
from typing import Set, Dict, List
import logging
from datetime import datetime, timezone, timedelta

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class EBSCleaner:
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
                        
            logger.info(f"Found {len(active_instances)} active instances")
            return active_instances
        except ClientError as e:
            logger.error(f"Error getting active instances: {str(e)}")
            raise

    def get_volumes_to_delete(self) -> List[Dict]:
        """
        Identify volumes that are not in use and older than retention period.
        
        Returns:
            List[Dict]: List of volumes to delete with their metadata
        """
        volumes_to_delete = []
        paginator = self.ec2.get_paginator('describe_volumes')
        retention_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)

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
                            'Age': (datetime.now(timezone.utc) - volume['CreateTime']).days
                        })

            logger.info(f"Found {len(volumes_to_delete)} unused volumes to delete")
            return volumes_to_delete
        except ClientError as e:
            logger.error(f"Error getting volumes: {str(e)}")
            raise

    def get_snapshots_to_delete(self) -> List[Dict]:
        """
        Identify snapshots that are orphaned (no volume) or from unused volumes.
        
        Returns:
            List[Dict]: List of snapshots to delete with their metadata
        """
        snapshots_to_delete = []
        paginator = self.ec2.get_paginator('describe_snapshots')
        retention_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        
        try:
            for page in paginator.paginate(OwnerIds=['self']):
                for snapshot in page['Snapshots']:
                    if snapshot['StartTime'] < retention_date:
                        if self._should_delete_snapshot(snapshot):
                            snapshots_to_delete.append({
                                'SnapshotId': snapshot['SnapshotId'],
                                'VolumeId': snapshot.get('VolumeId'),
                                'Age': (datetime.now(timezone.utc) - snapshot['StartTime']).days,
                                'Description': snapshot.get('Description', 'No description')
                            })
                        
            logger.info(f"Found {len(snapshots_to_delete)} snapshots to delete")
            return snapshots_to_delete
        except ClientError as e:
            logger.error(f"Error getting snapshots: {str(e)}")
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
            logger.info(f"Snapshot {snapshot['SnapshotId']} has no volume ID")
            return True
            
        try:
            volume_response = self.ec2.describe_volumes(VolumeIds=[volume_id])
            # Check if volume exists and has attachments
            return volume_response['Volumes'][0]['State'] == 'available'
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidVolume.NotFound':
                logger.info(f"Volume {volume_id} not found for snapshot {snapshot['SnapshotId']}")
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
                    f"Deleted volume {volume['VolumeId']}, "
                    f"Size: {volume['Size']}GB, "
                    f"Age: {volume['Age']} days"
                )
            except ClientError as e:
                logger.error(
                    f"Error deleting volume {volume['VolumeId']}: {str(e)}"
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
                    f"Deleted snapshot {snapshot['SnapshotId']}, "
                    f"Age: {snapshot['Age']} days, "
                    f"Description: {snapshot['Description']}"
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidSnapshot.InUse':
                    logger.warning(
                        f"Snapshot {snapshot['SnapshotId']} is in use, skipping deletion"
                    )
                else:
                    logger.error(
                        f"Error deleting snapshot {snapshot['SnapshotId']}: {str(e)}"
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
    except Exception as e:
        logger.error(f"Error in lambda execution: {str(e)}")
        raise