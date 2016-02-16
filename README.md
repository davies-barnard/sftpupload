# sftpupload
Secure FTP Upload Extension for Weewx over SSH.  This is not to be confused with Secure FTP.   
This is the way forward if you have SSH access and have rsync issues with compatible versions!

Copyright 2016 Chris Davies

Installation instructions:

0) This extension requires <a href="https://pypi.python.org/pypi/pysftp">pysftp</a>.
1) run the installer:

setup.py install --extension extensions/sftpupload
#./bin/wee_extension --install=extensions/sftpupload.tar.gz

2) restart weewx:

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start

Manual installation instructions:

1) copy files to the weewx user directory:

cp bin/user/sftpupload.py /home/weewx/bin/user
cp -R skins/SFtp /home/weewx/skins/

2) in weewx.conf, add the following section 

[StdReport]
  [[SFTP]]
    skin = SFtp
    HTML_ROOT = public_html
    user = yourUserName
    password = yourPassWord
    server = yourServer
    path = remotePath
    max_tries = 3

3) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start