class AWSSESRotate:
    '''These values are required to calculate the signature. Do not change them'''
    DATE = '11111111'
    SERVICE = 'ses'
    MESSAGE = 'SendRawEmail'
    TERMINAL = 'aws4_request'
    VERSION = 0x04
    def _init_(self, dry_run: bool, days: int, nowait: bool) -> None:
        self.ec2_config = EC2Config()
        self.dry_run = dry_run
        self.days = days
        self.verb = 'Would' if dry_run else 'Will'
        self.nowait = nowait
        self.account = self.ec2_config.account
        self.region = self.ec2_config.ec2_region or self.ec2_config.account_info()['default_region']
        self.boto_iam = self.ec2_config.get_boto('iam', account=self.account, region=self.region)

    def update_vault_ses_credentials(self, smtp_creds: dict) -> None:
        ''' Update the smtp username and password in vault '''
        creds = {
            'IAM User Name': smtp_creds['IAM User Name'],
            'STARTTLS Port': 587,
            'Smtp Host': smtp_creds['Smtp Host'],
            'Smtp Password': smtp_creds['Smtp Password'],
            'Smtp Username': smtp_creds['Smtp Username']
        }
        SECRETS.write_batch_secret('/beacon/keys/smtp/creds', creds)

    def sign(self, key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    def calculate_key(self, secret_access_key: str, region: str) -> str:
        ''' Decode the SES user secret access key '''
        signature = self.sign(("AWS4" + secret_access_key).encode(), self.DATE)
        signature = self.sign(signature, region)
        signature = self.sign(signature, self.SERVICE)
        signature = self.sign(signature, self.TERMINAL)
        signature = self.sign(signature, self.MESSAGE)
        signature_and_version = bytes([self.VERSION]) + signature
        smtp_password = base64.b64encode(signature_and_version)
        return smtp_password.decode()

    def rotate_ses_credentials(self) -> None:
        ''' Rotate current SES user credentials '''
        curr_smtp_creds = read_batch_secret('/beacon/keys/smtp/creds')
        new_smtp_creds = curr_smtp_creds.copy()
        iam_username = curr_smtp_creds['IAM User Name']
        smtp_username = curr_smtp_creds['Smtp Username']

        if curr_smtp_creds['Smtp Username'] == '':
            logger.warning('Domain is using wst SES creds, please migrate the domain to use own SES service')
            return

        access_keys = self.boto_iam.list_access_keys(UserName=iam_username)

        # Obtain the AccessKeyMetadata that matches to the current Smtp Username
        key_metadata = [x for x in access_keys['AccessKeyMetadata'] if x['AccessKeyId'] == curr_smtp_creds['Smtp Username'] and x['Status'] == 'Active']
        if key_metadata is None:
            logger.warning('Access key ID for %s does not match the existing key stored in Vault', iam_username)
            return
        if len(key_metadata) != 1:
            logger.warning(key_metadata)
            message = f'There are multiple access_keys associated to {iam_username} user which is unusual, please investigate it from the AWS console'
            raise RuntimeError(message)

        logger.info('%s rotate SES credential for IAM User: %s with AccessKeyId: %s',
                        self.verb, iam_username, smtp_username)

        time_diff = datetime.now(tzutc()) - key_metadata[0]['CreateDate'].astimezone(tzutc())
        days_diff = time_diff.days
        if not self.nowait and days_diff <= self.days:
            logger.info('%s not rotate the credentials because they are not older than %d days', self.verb, self.days)
            return
        if not self.dry_run:
            logger.info('Creating access key in the aws console for %s user', iam_username)
            new_access_key = self.boto_iam.create_access_key(UserName=iam_username)
            new_smtp_creds['IAM User Name'] = new_access_key['AccessKey']['UserName']
            new_smtp_creds['Smtp Username'] = new_access_key['AccessKey']['AccessKeyId']
            new_smtp_creds['Smtp Password'] = self.calculate_key(new_access_key['AccessKey']['SecretAccessKey'], self.region)
        logger.info('%s update credentials in vault for %s user', self.verb, iam_username)
        if not self.dry_run:
            self.update_vault_ses_credentials(new_smtp_creds)
        logger.info('%s update current access key in the aws console for %s user', self.verb, iam_username)
        if not self.dry_run:
            self.boto_iam.update_access_key(AccessKeyId=curr_smtp_creds['Smtp Username'], Status='Inactive', UserName=iam_username)
        logger.info('%s delete current access key in the aws console for %s user', self.verb, iam_username)
        if not self.dry_run:
            self.boto_iam.delete_access_key(AccessKeyId=curr_smtp_creds['Smtp Username'], UserName=iam_username)