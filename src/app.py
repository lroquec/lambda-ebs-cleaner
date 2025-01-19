from datetime import datetime, timezone, timedelta
import logging
from typing import Set, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class EBSCleaner:
    def __init__(self, retention_days: Optional[int] = None):
        self.ec2 = boto3.client('ec2')
        self.retention_days = retention_days

    def get_active_instance_ids(self) -> Set[str]:
        active_instances = set()
        paginator = self.ec2.get_paginator('describe_instances')

        try:
            for page in paginator.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        active_instances.add(instance['InstanceId'])

            logger.info('Found %d active instances', len(active_instances))
            return active_instances
        except ClientError as err:
            logger.error('Error getting active instances: %s', str(err))
            raise

    def get_volumes_to_delete(self) -> List[Dict]:
        volumes_to_delete = []
        paginator = self.ec2.get_paginator('describe_volumes')

        try:
            for page in paginator.paginate(Filters=[{'Name': 'status', 'Values': ['available']}]):
                for volume in page['Volumes']:
                    age_days = (datetime.now(timezone.utc) - volume['CreateTime']).days
                    
                    if self.retention_days is not None and age_days <= self.retention_days:
                        logger.info('Volume %s skipped: Too new (age: %d days)', volume['VolumeId'], age_days)
                        continue

                    volumes_to_delete.append({
                        'VolumeId': volume['VolumeId'],
                        'Size': volume['Size'],
                        'Age': age_days
                    })

            logger.info('Found %d unused volumes to delete', len(volumes_to_delete))
            return volumes_to_delete
        except ClientError as err:
            logger.error('Error getting volumes: %s', str(err))
            raise

    def get_snapshots_to_delete(self) -> List[Dict]:
        snapshots_to_delete = []
        paginator = self.ec2.get_paginator('describe_snapshots')

        try:
            for page in paginator.paginate(OwnerIds=['self']):
                for snapshot in page['Snapshots']:
                    logger.info(
                        'Checking snapshot %s (Volume: %s, StartTime: %s)',
                        snapshot['SnapshotId'],
                        snapshot.get('VolumeId', 'No Volume'),
                        snapshot['StartTime']
                    )
                    
                    snapshot_age = (datetime.now(timezone.utc) - snapshot['StartTime']).days

                    if self.retention_days is not None and snapshot_age <= self.retention_days:
                        logger.info('Snapshot %s skipped: Too new (age: %d days)', snapshot['SnapshotId'], snapshot_age)
                        continue

                    if self._should_delete_snapshot(snapshot):
                        snapshots_to_delete.append({
                            'SnapshotId': snapshot['SnapshotId'],
                            'VolumeId': snapshot.get('VolumeId'),
                            'Age': snapshot_age,
                            'Description': snapshot.get('Description', 'No description')
                        })

            logger.info('Found %d snapshots to delete', len(snapshots_to_delete))
            return snapshots_to_delete
        except ClientError as err:
            logger.error('Error getting snapshots: %s', str(err))
            raise

    def _should_delete_snapshot(self, snapshot: Dict) -> bool:
        volume_id = snapshot.get('VolumeId')

        if not volume_id:
            logger.info('Snapshot %s marked for deletion: No volume ID', snapshot['SnapshotId'])
            return True

        try:
            volume_response = self.ec2.describe_volumes(VolumeIds=[volume_id])
            volume_state = volume_response['Volumes'][0]['State']
            
            if volume_state == 'available':
                logger.info('Snapshot %s marked for deletion: Volume %s is available', snapshot['SnapshotId'], volume_id)
                return True
            
            logger.info('Snapshot %s kept: Volume %s is in use (state: %s)', snapshot['SnapshotId'], volume_id, volume_state)
            return False
            
        except ClientError as err:
            if err.response['Error']['Code'] == 'InvalidVolume.NotFound':
                logger.info('Snapshot %s marked for deletion: Volume %s not found', snapshot['SnapshotId'], volume_id)
                return True
            raise

    def delete_volumes(self, volumes: List[Dict]) -> None:
        for volume in volumes:
            try:
                self.ec2.delete_volume(VolumeId=volume['VolumeId'])
                logger.info('Deleted volume %s, Size: %sGB, Age: %s days', 
                          volume['VolumeId'], volume['Size'], volume['Age'])
            except ClientError as err:
                logger.error('Error deleting volume %s: %s', volume['VolumeId'], str(err))

    def delete_snapshots(self, snapshots: List[Dict]) -> None:
        for snapshot in snapshots:
            try:
                self.ec2.delete_snapshot(SnapshotId=snapshot['SnapshotId'])
                logger.info('Deleted snapshot %s, Age: %s days, Description: %s',
                          snapshot['SnapshotId'], snapshot['Age'], snapshot['Description'])
            except ClientError as err:
                if err.response['Error']['Code'] == 'InvalidSnapshot.InUse':
                    logger.warning('Snapshot %s is in use, skipping deletion', snapshot['SnapshotId'])
                else:
                    logger.error('Error deleting snapshot %s: %s', snapshot['SnapshotId'], str(err))


def lambda_handler(event: Dict, _context: Dict) -> Dict:
    try:
        retention_days = event.get('retention_days', 7)
        cleaner = EBSCleaner(retention_days if retention_days > 0 else None)

        volumes_to_delete = cleaner.get_volumes_to_delete()
        cleaner.delete_volumes(volumes_to_delete)

        snapshots_to_delete = cleaner.get_snapshots_to_delete()
        cleaner.delete_snapshots(snapshots_to_delete)

        return {
            'statusCode': 200,
            'body': f'Successfully processed {len(volumes_to_delete)} volumes and {len(snapshots_to_delete)} snapshots'
        }
    except Exception as err:
        logger.error('Error in lambda execution: %s', str(err))
        raise
