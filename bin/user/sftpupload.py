#
#   Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#   Modified by Chris Davies-Barnard <weewx@davies-barnard.co.uk> to include sftp support.  Requires pysftp
#
#   See the file LICENSE.txt for your full rights.
#
"""For uploading files to a remove server via FTP"""

from __future__ import with_statement
import os
import sys
import ftplib
import cPickle
import time
import syslog
import weewx

from weeutil.weeutil import to_bool
#Try to import pysftp for a really secure connection and fail garcefully.
try:
  import pysftp as sftp
except ImportError:
  syslog.syslog(syslog.LOG_CRIT, "sftpupload: Requires pysftp : %s" % e)
  pass
  
class SFtpGenerator(weewx.reportengine.ReportGenerator):
    """Class for managing the "SFTP generator".
    
    This will sftp everything in the public_html subdirectory to a webserver."""

    def run(self):
        import user.sftpupload

        # determine how much logging is desired
        log_success = to_bool(self.skin_dict.get('log_success', True))

        t1 = time.time()

        if self.skin_dict.has_key('HTML_ROOT'):
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.skin_dict['HTML_ROOT'])
        else:
            local_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      self.config_dict['StdReport']['HTML_ROOT'])
        try:

            print(self.config_dict)
            print(self.skin_dict)
            """Initialize an instance of FtpUpload.
            After initializing, call method run() to perform the upload."""
            sftpData = SFTPUpload(
  
              #print(config_dict)
              #server: The remote server to which the files are to be uploaded.
              server = self.skin_dict['server'],
    
              #user, password : The user name and password that are to be used.
              user  = self.skin_dict['user'],
              password = self.skin_dict['password'],

              #the local_root of the weewx public_html files.
              local_root   = local_root,

              #the remote path we are looking to upload to.
              remote_root  = self.skin_dict.get('path', 'public_html'),

              #name: A unique name to be given for this FTP session. This allows more
              #than one session to be uploading from the same local directory. [Optional.
              #Default is 'FTP'.]
              name = 'SFTP',

              #max_tries: How many times to try creating a directory or uploading
              #a file before giving up [Optional. Default is 3]
              max_tries   = int(self.skin_dict.get('max_tries', 3)),

              #debug: Set to 1 for extra debug information, 0 otherwise.
              debug = int(self.config_dict.get('debug', 1))

            ) #End SFTPUploader Initialisation.

        except Exception, e:
            syslog.syslog(syslog.LOG_DEBUG, "sftp-reportengine: SFTP upload not requested. Skipped.")
            print(e)
            return

        try:
            N = sftpData.run()
        except (socket.timeout, socket.gaierror, ftplib.all_errors, IOError), e:
            (cl, unused_ob, unused_tr) = sys.exc_info()
            syslog.syslog(syslog.LOG_ERR, "sftp-reportengine: Caught exception %s in SFtpGenerator; %s." % (cl, e))
            weeutil.weeutil.log_traceback("        ****  ")
            return
        
        t2= time.time()
        if log_success:
            syslog.syslog(syslog.LOG_INFO, """sftp-reportengine: sftp'd %d files in %0.2f seconds""" % (N, (t2-t1)))


class SFTPUpload(object):
  """Uploads a directory and all its descendants to a remote server.
  
  Keeps track of when a file was last uploaded, so it is uploaded only
  if its modification time is newer."""

  def __init__(self, server, 
                 user, password, 
                 local_root, remote_root, 
                 name      = "SFTP", 
                 max_tries = 3,
                 debug     = 0):

    self.server      = server
    self.user        = user
    self.password    = password
    self.local_root  = os.path.normpath(local_root)
    self.remote_root = os.path.normpath(remote_root)
    self.name        = name
    self.max_tries   = max_tries
    self.debug       = debug

    
  
  def run(self):
    """Perform the actual upload.
    returns: the number of files uploaded."""

    #We have a request for a secure connection.  Is this standard secure FTP or SFTP over SSH?
    if self.debug:
      syslog.syslog(syslog.LOG_DEBUG, "sftpupload: Trying sFTP with pysftp library.")
      self.sFTP = True
            
    # Get the timestamp and members of the last upload:
    (timestamp, fileset) = self.getLastUpload()

    n_uploaded = 0
    # Try to connect to the ftp server up to max_tries times: 
    try:
      
      #What are we attempting?
      syslog.syslog(syslog.LOG_NOTICE, "sftpupload: Attempting %d times a sFTP connection to %s." % (self.max_tries,self.server))
          
      #For all our max tries
      for count in range(self.max_tries):
        try:
          ftp_server = sftp.Connection(host=self.server, username=self.user, password=self.password, log=True)
          syslog.syslog(syslog.LOG_DEBUG, "stpupload: Attempt : %d, %s" % (count,ftp_server.logfile))
          break
        except sftp.ConnectionException, e:
          syslog.syslog(syslog.LOG_CRIT, "sftpupload: Unable to connect or log into sFTP server : %s" % e)

      # This is executed only if the loop terminates naturally (without a break statement),
      # meaning the ftp connection failed max_tries times. Abandon ftp upload
      else:
        syslog.syslog(syslog.LOG_CRIT, 
          "sftpupload: Attempted %d times to connect to server %s. Giving up." % 
          (self.max_tries, self.server))
        return n_uploaded


      # Now for the upload
      #Walk the local directory structure
      for (dirpath, unused_dirnames, filenames) in os.walk(self.local_root):

        # Strip out the common local root directory. What is left
        # will be the relative directory both locally and remotely.
        local_rel_dir_path = dirpath.replace(self.local_root, '.')
        if self._skipThisDir(local_rel_dir_path):
          continue
        
        # This is the absolute path to the remote directory:
        remote_dir_path = os.path.normpath(os.path.join(self.remote_root, local_rel_dir_path))

        # Make the remote directory if necessary:
        self._sftp_make_remote_dir(ftp_server, remote_dir_path)

        
        # Now iterate over all members of the local directory:
        for filename in filenames:

          full_local_path = os.path.join(dirpath, filename)
          # See if this file can be skipped:
          if self._skipThisFile(timestamp, fileset, full_local_path):
            continue

          full_remote_path = os.path.join(remote_dir_path, filename)
          STOR_cmd = "STOR %s" % full_remote_path
          
          # Retry up to max_tries times:
          for count in range(self.max_tries):
            
            try:
              ftp_server.put(full_local_path,full_remote_path)
            except IOError as ie:
              syslog.syslog(syslog.LOG_ERR, "sftpupload: Attempt #%d. IO Failed uploading %s to %s. Reason: %s" %
                (count+1, full_remote_path, self.server, ie))
            except OSError as oe:
              syslog.syslog(syslog.LOG_ERR, "sftpupload: Attempt #%d. OS Failed uploading %s to %s. Reason: %s" %
                (count+1, full_local_path, self.server, oe))
            else:
              # Success. Log it, break out of the loop
              n_uploaded += 1
              fileset.add(full_local_path)
              syslog.syslog(syslog.LOG_DEBUG, "sftpupload: Uploaded file %s" % full_remote_path)
              break
            finally:
              # This is always executed on every loop. Close the file.
              try:
                fd.close()
              except:
                pass

          else:
            # This is executed only if the loop terminates naturally (without a break statement),
            # meaning the upload failed max_tries times. Log it, move on to the next file.
            syslog.syslog(syslog.LOG_ERR, "sftpupload: Failed to upload file %s" % full_remote_path)
    finally:
      try:
        ftp_server.quit()
      except:
        pass
    
    timestamp = time.time()
    self.saveLastUpload(timestamp, fileset)
    return n_uploaded
  
  def getLastUpload(self):
    """Reads the time and members of the last upload from the local root"""
    
    #A Filestamp file is used to log what happens during this process.
    timeStampFile = os.path.join(self.local_root, "#%s.last" % self.name )

    # If the file does not exist, an IOError exception will be raised. 
    # If the file exists, but is truncated, an EOFError will be raised.
    # Either way, be prepared to catch it.
    try:
      with open(timeStampFile, "r") as f:
        timestamp = cPickle.load(f)
        fileset  = cPickle.load(f) 
    except (IOError, EOFError, cPickle.PickleError):
      timestamp = 0
      fileset = set()
      # Either the file does not exist, or it is garbled.
      # Either way, it's safe to remove it.
      try:
        os.remove(timeStampFile)
      except OSError:
        pass
    
    #If we are debugging lets start by printing out the date so its readable with a ts for comparison.
    if self.debug:
      import datetime
      lastupload = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
      print ("Last SFTP UPLOAD was: %s (%d)" %(lastupload,timestamp))
    
    #Return the timestamp of the last upload and the set of files previously uploaded.
    return (timestamp, fileset)


  def saveLastUpload(self, timestamp, fileset):
    """Saves the time and members of the last upload in the local root."""
    timeStampFile = os.path.join(self.local_root, "#%s.last" % self.name )
    with open(timeStampFile, "w") as f:
      cPickle.dump(timestamp, f)
      cPickle.dump(fileset,  f)

  #Added for the sFTP connections.
  def _sftp_make_remote_dir(self, ftp_server, remote_dir_path):
    """Make a remote directory if necessary."""
    # Try to make the remote directory up max_tries times, then give up.
    for unused_count in range(self.max_tries):
      try:
        if not ftp_server.isdir(remote_dir_path):
          ftp_server.mkdir(remote_dir_path)
      except OSError:
        pass
    
    
    
  def _skipThisDir(self, local_dir):
    return os.path.basename(local_dir) in ('.svn', 'CVS')

  def _skipThisFile(self, timestamp, fileset, full_local_path):
    """This method checks the last upload timestamp against that last modified time in the file
     and returns True if the file can be skipped.  If also checks if it has previously been uploaded. """

    #Get our real filename from the local path
    filename = os.path.basename(full_local_path)

    #Ok, this is not a real file or atleast one for copying.
    if filename[-1] == '~' or filename[0] == '#' :
      return True
    
    flag = True
    #Does the file not appear in the fileset?
    if full_local_path not in fileset:
      flag = False
    
    #Has the file been updated/changed since last upload?
    ftime = os.stat(full_local_path).st_mtime
    if ftime > timestamp:
      flag = False
    
    #Are we debugging?
    if self.debug:
      print ("%s:%d vs %d = %s"%(full_local_path,ftime,timestamp,str(flag))) 
    
    # Filename is in the set (has been copied), and is up to date (not changed).
    return flag

    

#Test function for the sftp
#PYTHONPATH=bin python bin/user/sftpupload.py weewx.conf 
if __name__ == '__main__':
  
  import weewx
  import socket
  import configobj
  
  weewx.debug = 1
  syslog.openlog('wee_sftpupload', syslog.LOG_PID|syslog.LOG_CONS)
  syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

  if len(sys.argv) < 2 :
    print """Usage: sftpupload.py path-to-configuration-file"""
    sys.exit(weewx.CMD_ERROR)
  
  try :
    config_dict = configobj.ConfigObj(sys.argv[1], file_error=True)
    skin_dict = config_dict['StdReport']['SFTP']
  except IOError:
    print "Unable to open configuration file ", sys.argv[1]
    raise

  socket.setdefaulttimeout(10)


  ftp_upload = SFtpGenerator(config_dict, skin_dict, gen_ts=None, first_run=None, stn_info=None)
  ftp_upload.run()
  
