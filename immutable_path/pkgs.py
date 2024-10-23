import logging
import re
from email.message import EmailMessage

from botocore.exceptions import ClientError
import BobConfigs
import ConfigEnv
import cached_property
import smtp
import retry_function

logger = logging.getLogger(__name__)


class MigratePackages:

    def __init__(self, dry_run=False):
        self.account_info = account_info
        self.s3 = self.account_info.s3_api
        self.domain = domain
        self.bucket = account_info.s3_bucket
        self.storage_url = account_info.storage_container_url
        self.dry_run = dry_run
        self.verb = 'Would' if dry_run else 'Will'
        self.infra_dir_content = {}
        self.infra_temp_dir_content = {}

    @cached_property
    def files_obj_list(self):
        files_obj_list = [name.get('Key') for name in self.s3.list_objects(
            bucket=self.bucket, prefix=f'domains/{self.domain}/configs/')]
        files_obj_list += [name.get('Key') for name in self.s3.list_objects(bucket=self.bucket,
            prefix=f'domains/{self.domain}/build/')]
        return files_obj_list

    def _copy_infra_files(self, temp_dir='infra_temp'):
        for value in self.infra_temp_dir_content.values():
            source_url = f'{self.storage_url}/{value}'
            dest_url = re.sub(f'/{temp_dir}/', '/infra/', f'{self.storage_url}/{value}', count=1)
            try:
                self._copy_files(source_url=source_url, dest_url=dest_url)
            except Exception:
                logger.exception('Failed to copy object')

    def _copy_files(self, source_url=None, dest_url=None):
        try:
            logger.info('%s copy %s to %s', self.verb, source_url, dest_url)
            if not self.dry_run:
                self.s3.copy_object2(source_url=source_url, dest_url=dest_url)
        except Exception:
            logger.exception('Failed to copy object')

    def _backup_and_delete_files(self, files=None):
        for value in files:
            try:
                source_url = f'{self.storage_url}/{value}'
                dest_url = re.sub(r'/infra/', '/infra_backup/', f'{self.storage_url}/{value}', count=1)
                logger.info('%s copy %s to %s', self.verb, source_url, dest_url)
                self._copy_files(source_url=source_url, dest_url=dest_url)
            except Exception:
                logger.exception('Failed to copy object')
        for value in files:
            try:
                logger.info('%s delete %s/%s', self.verb, source_url, dest_url)
                if not self.dry_run:
                    self.s3.del_object(bucket=self.bucket, key=value)
                    retry_config = {
                        'backoff': 'exponential',
                        'max_retries': 10,
                        'start_interval': 1,
                        'factor': 2,
                        'max_interval': 60,
                        'total_interval': 300,
                    }
                    def check_object_deleted():
                        try:
                            self.s3.head_object(bucket=self.bucket, key=value)
                        except ClientError as e:
                            if e.response['Error']['Code'] == '404':
                                logger.info('Object %s not found, it has been successfully deleted.', value)
                                return
                            else:
                                raise e
                    retry_function(
                            retry_config=retry_config,
                            f=check_object_deleted,
                            exception_list=(ClientError,),
                    )      
            except Exception:
                logger.exception('Unexpected error during object deletion')

    def _send_diff_email(self, files=None):
        from_address = None
        files_html = "<table border='1' style='border-collapse: collapse;'>"
        files_html += "<tr><th>Files</th></tr>"

        for value in files:
            files_html += f"<tr><td>{value}</td></tr>"

        files_html += "</table>"

        if not from_address:
            from_address = email_from

        msg = EmailMessage()
        cenv = ConfigEnv()
        msg['Subject'] = f'Files migrated by the migration script for {domain}'
        msg['From'] = from_address
        msg['To'] = to_address
        files_info = f"""
            <html>
            <head></head>
            <body>
                <p>Hi,</p>
                <p>Here are the files migrated by the migration script for {domain}</p>
                {files_html}
                <p>Best regards,<br>Beacon Platform Engineering</p>
            </body>
            </html>
        """
        msg.add_alternative(files_info, subtype='html')
        with smtp() as s:
            if not self.dry_run:
                s.send_message(msg)

    def _check_extra_files(self, regex=None, temp_dir='infra_temp'):
        def fetch_s3_objects(bucket, prefix, temp_dir=None):
            objects = {}
            for res in self.s3.list_objects(bucket=self.bucket, prefix=prefix):
                key = res.get('Key')
                if key:
                    modified_key = key.replace(temp_dir, 'infra') if temp_dir and temp_dir in key else key
                    objects[modified_key] = key
            return objects
        self.infra_dir_content.update(fetch_s3_objects(bucket=self.bucket, prefix=f'infra/{self.domain}/build/'))
        self.infra_dir_content.update(fetch_s3_objects(bucket=self.bucket, prefix=f'infra/{self.domain}/configs/'))
        self.infra_temp_dir_content.update(fetch_s3_objects(bucket=self.bucket, prefix=f'{temp_dir}/{self.domain}/build/', temp_dir=temp_dir))
        self.infra_temp_dir_content.update(fetch_s3_objects(bucket=self.bucket, prefix=f'{temp_dir}/{self.domain}/configs/', temp_dir=temp_dir))
        diff_files_keys = self.infra_dir_content.keys() - self.infra_temp_dir_content.keys()
        diff_files = {key: self.infra_dir_content.get(key, None) for key in diff_files_keys}
        return diff_files.values()

    def migrate_files(self, regex=None, temp_dir='infra_temp'):
        for obj in self.files_obj_list:
            for pattern in regex:
                if re.search(pattern, obj):
                    source_url = f'{self.storage_url}/{obj}'
                    dest_url = re.sub(r'/domains/', f'/{temp_dir}/', f'{self.storage_url}/{obj}', count=1)
                    self._copy_files(source_url=source_url, dest_url=dest_url)
        extra_files = self._check_extra_files(regex=regex, temp_dir=temp_dir)
        if len(extra_files) == 0:
            logger.info('No Additional Packages')
        else:
            self._send_diff_email(files=extra_files)
            self._backup_and_delete_files(files=extra_files)
        self._copy_infra_files(temp_dir=temp_dir)