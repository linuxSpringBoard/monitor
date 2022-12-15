#!/bin/bash

log() {
    echo "`date '+%Y%m%d %H:%M:%S'`: $1"
}

failOnError() {
    if [ $? -ne 0 ]; then
    log "FAILURE: $1. Aborting"
    exit -1
    fi
    log "COMPLETED: $1"
}

mkdirp() {
    mkdir -p $1
    failOnError "Creating Directory: $1"
}

createSymlink() {
    TARGET=$1
    LINKNAME=$2
    if [ -e $TARGET ]; then
    ln -nfs $TARGET $LINKNAME
    failOnError "Create symlink $LINKNAME -> $TARGET"
    else
    log "WARN: $TARGET not found for link $LINKNAME"
    fi
}

stopProcess() {
    pid=`ps -eaf | grep "$2" | grep "$3" | grep -v grep | awk '{print $2}'`
    if [ -z $pid ]
    then
    log "Process $1 is not running"
    else
    log "Process $1 running with PID: ${pid}. Killing it."
    kill -9 $pid
    fi
}

rotateLog(){
    if [ -f $1 ]; then
        current_time=$(date "+%Y.%m.%d-%H.%M.%S")
        new_fileName=$1.$current_time
        log "New log fileName: $new_fileName"
        mv $1 $new_fileName
    else
        log "Log file $1 does not exist"
    fi
    log "Creating new log file"
    touch $1
}

removeCron() {
    if [ -z "$1" ]; then
        log "command $1 is empty or null"
        exit 1
    fi
    echo "########## Crontab BEFORE ##############"
    crontab -l
    crontab -l | grep -v "$1" > /tmp/oldcron
    crontab /tmp/oldcron
    echo "########## Crontab AFTER ##############"
    crontab -l
}

addCron() {
    if [ -z "$1" ]; then
      log "command $1 is empty or null"
      exit 1
    fi
    if [ -z "$2" ]; then
      log "frequency $2 is empty or null"
      exit 1
    fi
    log "Taking a backup of old cron at /tmp/oldcron"
    crontab -l > /tmp/oldcron
    cat /tmp/oldcron
    log "now appending to existing crontab if any"
    log "$2 $1 > /dev/null 2>&1" >> /tmp/oldcron
    log "now adding $2 $1 > /dev/null 2>&1 to crontab for `id`"
    cat /tmp/oldcron
    crontab /tmp/oldcron
}

  log "Initiating Start script"
  rotateLog /local/scratch/monitor-dashboard/logs/heartbeat.log
  touch /local/scratch/monitor-dashboard/report/report.html
  touch /local/scratch/monitor-dashboard/report/reportHost.html

  log "Report Files created"
  cd /local/scratch/monitor-dashboard/scripts

  nohup /usr/bin/python3 hb.py >/dev/null &
  #nohup /usr/bin/python3 -m http.server 8000 >/dev/null &
  nohup /usr/bin/python3 -u /local/scratch/monitor-dashboard/scripts/start.py 2>/local/scratch/monitor-dashboard/logs/server.txt &
  log "Finished Start script"
