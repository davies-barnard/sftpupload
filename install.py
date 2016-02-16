# Installer for SFTPUpload
# Copyright 2016 Chris Davies

from setup import ExtensionInstaller

def loader():
	return SFTPUploadInstaller()

class SFTPUploadInstaller(ExtensionInstaller):
	def __init__(self):
		super(SFTPUploadInstaller, self).__init__(
			version='0.1',
			name='sftpupload',
			description='A true secure FTP uploader for Weewx.  Requires pysftp',
			author='Chris Davies',
			author_email='weewx@davies-barnard.co.uk',
			config={
				'StdReport': {
						'SFTP': {
								'skin': 'SFtp',
								'user': 'yourUserName',
                'password':'yourPassWord',
                'server':'yourServer',
                'path':'remotePath',
                'max_tries' = 3,
								'HTML_ROOT': 'public_html'
						}
				}
			},
			files=[
				('bin/user', ['bin/user/sftpupload.py']),
				('skins/SFtp', ['skins/SFtp/skin.conf']),
			]
		)