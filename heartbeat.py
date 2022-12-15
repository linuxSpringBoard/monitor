# A simple python utility to monitor uptime of given urls
# Reads config from config.json file and pings eachs of the given URLs in 5 min intervals
# Start this script as a daemon by adding & at the end of invocation so that it can run in background

from http.client import InvalidURL
import json
import logging
import ssl
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import time
from collections import OrderedDict
import subprocess
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime
import traceback

hostList = []

# logging configuration
logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
        filename='../logs/heartbeat.log',
        filemode='a',
        datefmt='%Y-%m-%d %H:%M:%S')



class Api:
        def __init__(self, name, url, env):
                self.name = name
                self.baseurl = url
                self.url = self.baseurl + 'internal/swagger'
                self.env = env
                self.commitId = ""
                self.prevCommitId = ""
                self.history = LimitedSizeDict()

        def ping(self,firstRun):
                try:
                        apiurl = urlopen(self.baseurl + 'actuator/health', timeout = 5)
                        output = json.loads(apiurl.read())
                        if 'status' in output and output['status'] == 'UP':
                                self.getCommitId()
                                if firstRun:
                                        self.history.__setitem__('UP')
                                elif self.commitId == self.prevCommitId:
                                        self.history.__setitem__('UP')
                                else:
                                        self.history.__setitem__('NEW')
                                return True
                        else:
                                self.history.__setitem__('DOWN')
                                return False
                except ssl.CertificateError as e:
                        logging.error('Received SSL error code ')
                        self.history.__setitem__('SSL_ERROR')
                        return False
                except HTTPError as e:
                        logging.error('Received return code %s' % str(e.code))
                        self.history.__setitem__('DOWN')
                        return False
                except URLError as e:
                        logging.error('Unknown error in connection ' + str(e.reason))
                        self.history.__setitem__('UNKNOWN')
                        return False
                except InvalidURL as e:
                        logging.error('URL invalid')
                        self.history.__setitem__('UNKNOWN')
                        return False
                except Exception:
                        logging.error('Generic error: ' + traceback.format_exc())
                        self.history.__setitem__('UNKNOWN')
                        return False

        def getCommitId(self):
                apiurl = urlopen(self.baseurl + 'actuator/info', timeout = 5)
                output = json.loads(apiurl.read())
                self.prevCommitId = self.commitId
                self.commitId = output['git']['commit']['id']
                logging.debug("[%s] %s Identified commit id is :: %s " % (self.env, self.name, self.commitId))


class Server:
        def __init__(self, name, url, env):
                self.name = name
                self.url = url
                self.env = env
                self.commitId = ""
                self.history = LimitedSizeDict()

        def ping(self,firstRun):
                try:
                        logging.debug('Trying to open URL :: %s' % self.url)
                        conn = urlopen(self.url, timeout = 5)
                        logging.debug('Connection Status :: ' + str(conn.status))
                except HTTPError as e:
                        logging.error('Received return code %s' % str(e.code))
                        self.history.__setitem__('DOWN')
                        return False
                except ssl.CertificateError as e:
                        logging.error('Received SSL error code ')
                        self.history.__setitem__('SSL_ERROR')
                        return False
                except InvalidURL as e:
                        logging.error('URL invalid')
                        self.history.__setitem__('UNKNOWN')
                        return False
                except URLError as e:
                        logging.error('Unknown error in connection ' + str(e.reason))
                        self.history.__setitem__('UNKNOWN')
                        return False
                except Exception:
                        logging.error('Generic error: ' + traceback.format_exc())
                        self.history.__setitem__('UNKNOWN')
                        return False
                else:
                        self.history.__setitem__('UP')
                        return True

class Process:
        def __init__(self, name, url, env):
                self.name = name
                self.url = url
                self.env = env
                self.commitId = ""
                self.history = LimitedSizeDict()
        def ping(self,firstRun=0):
                cmd = 'nc -zv ' + self.url
                output = subprocess.getoutput(cmd)
                if 'Connected' in output:
                        logging.debug(self.name,' is up')
                        self.history.__setitem__('UP')
                        return True
                else:
                        logging.error(self.name ,' is down with error', str(output))
                        self.history.__setitem__('DOWN')
                        return False

class MultiHost:
        def __init__(self, name, url, env, cookie, rep):
                self.name = name
                self.nimbus = url
                self.url = "https://" + url + "/internal/swagger"
                self.env = env
                self.cookie = cookie
                self.history = LimitedSizeDict()
                self.repHost = rep

        def checkList(self, serviceName, host, port):
                name = serviceName + ' ' + host
                for i in hostList:
                        if i.name == name:
                                return i
                purl = host + ' ' + port
                newUrl = Process(name, purl, self.env)
                hostList.append(newUrl)
                return newUrl

        def ping(self, firstRun):
                nimbus,port = self.nimbus.split(":")
                requestURL = 'http://nimbus.gs.com/api/v3/vservers/'+ nimbus
                logging.debug(requestURL)
                try:
                        bashCMD = f"curl -X GET -b {self.cookie} '{requestURL}' -H 'accept: application/json'"
                        response = subprocess.run(bashCMD,check=True,shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE,universal_newlines=True)
                        response = response.stdout
                        responseJSON = json.loads(response)
                except:
                        logging.error("Something went wrong while checking health for " , str(nimbus))
                count = 0
                try:
                        for i in responseJSON['content']['realServers']:
                                newUrl = self.checkList(self.name, i['data'], port)
                                if newUrl.ping():
                                        count = count + 1
                                self.repHost.append(newUrl)
                                logging.debug('Appended to repHost ',str(self.name))
                        if(responseJSON['content']['state'] == 'UP'):
                                self.history.__setitem__('UP')
                                return True
                        else:
                                self.history.__setitem__('DOWN')
                                return False
                except:
                        logging.error("Something went wrong while parsing the JSON response for " , str(nimbus), " nimbus URL")

class LimitedSizeDict(OrderedDict):
        def __init__(self, *args, **kwds):
                self.size_limit = kwds.pop("size_limit", 50)
                OrderedDict.__init__(self, *args, **kwds)
                self._check_size_limit()

        def __setitem__(self, value):
                key = time.time()
                OrderedDict.__setitem__(self, key, value)
                self._check_size_limit()

        def _countitem(self, item):
                count = 0
                for a,b in self.items():
                        if b == item:
                                count +=1
                return count

        def _check_size_limit(self):
                if self.size_limit is not None:
                        while len(self) > self.size_limit:
                                self.popitem(last=False)


class Report:
        def __init__(self, fileName):
                self.htmlTarget = fileName
                self.summary = ""
                self.footer = ""
                self.header = """<html>
<head>
<meta http-equiv="content-style-type" content="text/css"><link  rel="stylesheet" href="./report.css" />
<meta http-equiv="refresh" content="30">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
</head>
<body><h1 class="bg-info no-margin-bottom text-white" align="center" style="line-height:2">
<i class="fa fa-heartbeat"></i> Non-Prod ECG Dashboard</h1>
<table class="table">
<tr align = "center" style="width:200%; valign="middle"">
        <td style="PADDING-RIGHT: 15.75pt; BACKGROUND: #2caa2c; width:25%">UP</td>
        <td style="PADDING-RIGHT: 15.75pt; BACKGROUND: #C41E3A; width:25%">DOWN</td>
        <td style="PADDING-RIGHT: 15.75pt; BACKGROUND: #FFFF00; width:25%">SSL_ERROR</td>
        <td style="PADDING-RIGHT: 15.75pt; BACKGROUND: #A9A9A9; width:25%">UNKNOWN</td>
</tr>
</table>

<table class="table">
<thead><th>Service</th><th>Uptime(last 4 hours)</th><th>Timeline(5 min intervals) Now
<i class="fa fa-arrow-circle-left"></i> TO <i class="fa fa-arrow-circle-right"></i> 4 hours ago</th></thead><tbody>"""

                self.emailSummary = ""
                self.emailHeader =  """<html>
<meta http-equiv="Content-Type" content="text/html; charset=us-ascii">
<div id="div_Header" style="width: 100%">
        <table style="WIDTH:100%" cellspacing="0" cellpadding="0" width="100%" border="0">
                <tr style="HEIGHT:49.5pt;">
                        <td style="PADDING-RIGHT: 29px; PADDING-LEFT: 0in; PADDING-BOTTOM: 0in; WIDTH: 1%; PADDING-TOP: 0in; HEIGHT: 49.5pt"
                                width="1%">
                                <p><span><img height="66" alt=" " src="http://home.web.gs.com/l.gif" NOSEND="1"></span></p>
                        </td>
                        <td style="PADDING-RIGHT: 15.75pt; PADDING-LEFT: 0in; BACKGROUND: #00355f; PADDING-BOTTOM: 0in; WIDTH: 97%; PADDING-TOP: 0in; HEIGHT: 49.5pt"
                                width="98%">
                                <p style="Text-Align:center; font-size:26px; font-family:Verdana; color:#FFFFFF;">
                                        <span> ECG REPORT</span>
                                </p>
                        </td>
                        <td style="PADDING-RIGHT: 22.5pt; PADDING-LEFT: 0in; BACKGROUND: #00355f; PADDING-BOTTOM: 0in; WIDTH: 49.5pt; PADDING-TOP: 0in; HEIGHT: 49.5pt"
                                width="66">
                                <p style="TEXT-ALIGN: right" align="right"></p>
                        </td>
                </tr>
        </table>
</div><br>"""
                self.emailFooter = "</html>"
                self.intHealth = 0
                self.qaHealth = 0
                self.uatHealth = 0
                self.betaHealth = 0

        def append(self, urlObj):
                if urlObj.history.__len__() > 0:
                        availability = (urlObj.history._countitem('UP')+urlObj.history._countitem('NEW'))/urlObj.history.__len__()*100
                        availability = round(availability, 2)
                else:
                        availability = 0
                environmentFlag = 0
                flag = 0
                if urlObj.env != "UAT":
                        self.emailSummary += ('<tr><td align="left" style="width: 200px; overflow: hidden;">%s</td>' % (urlObj.name))
                else:
                        environmentFlag = 1
                self.summary += ('<tr> <td><a href="%s">%s</a></td>' % (urlObj.url, urlObj.name))
                self.summary += ('<td> %s %% </td><td>' % availability)
                downTime = 0
                count = 0
                for a, b in sorted(urlObj.history.items(), reverse=True):
                        self.summary += ('<i class="fa fa-square %s " title=" %s ">' % (b, time.ctime(a)))
                        if flag == 0 and environmentFlag == 0:
                                flag = 1
                                if b == "UP":
                                        self.emailSummary += ('<td align="center" bgcolor = "#2caa2c" style="width: 100px; overflow: hidden;">%s</td>' % (b))
                                elif b == "DOWN":
                                        self.emailSummary += ('<td align="center" bgcolor = "#C41E3A" style="width: 100px; overflow: hidden;">%s</td>' % (b))
                                elif b == "SSL_ERROR":
                                        self.emailSummary += ('<td align="center" bgcolor = "#FFFF00" style="width: 100px; overflow: hidden;">%s</td>' % (b))
                                elif b == "UNKNOWN":
                                        self.emailSummary += ('<td align="center" bgcolor = "#A9A9A9" style="width: 100px; overflow: hidden;">%s</td>' % (b))

                        if b != "UP" and count < 2:
                                downTime += 1

                        if downTime == 1:
                                if urlObj.env == "QA":
                                        self.qaHealth = 1
                                if urlObj.env == "UAT":
                                        self.uatHealth = 1
                                if urlObj.env == "BETA":
                                        self.betaHealth = 1

                        if downTime == 2:
                                if urlObj.env == "INT":
                                        self.intHealth = 1

                        count += 1

                self.summary += '</td> </tr>'
                self.emailSummary += '</tr>'
                return

        def flush(self):
                self.summary = ""
                logging.debug('Flushed stale data from report')
                return

        def print(self):
                timestr = time.ctime()
                self.footer = "</tbody></table>"
                self.footer += ('<h2 class="bg-primary text-white" style="line-height:1.5"> <i class="fa fa-clock-o"></i> Report generated at %s EST </h2></body></html>' % timestr)
#         logging.debug('Opening report html for writing')
                logging.debug('Opening report html for writing: ', str(self.htmlTarget))
                f = open(self.htmlTarget, "w")
                f.write(self.header + self.summary + self.footer)
                f.close()
                return

        def sendMail(self, environment):

                me = "gs-am-it-digital-sma-devops@internal.email.gs.com"
                you = ["gs-am-it-digital-sma-devops@internal.email.gs.com", "eishaan.singh@ny.email.gs.com"]
                # Creating message container - the correct MIME type is multipart/alternative.
                msg = MIMEMultipart('alternative')
                msg['Subject'] = ('Alert: %s Env is un-healthy' % (environment))
                msg['From'] = me
                msg['To'] = ", ".join(you)
                emailText = "Please see the detailed report here - https://dev.ecg-dashboard.gsam-sma.nimbus.gs.com:8000/report.html"
                part = MIMEText(emailText, 'html')
                msg.attach(part)
                s = smtplib.SMTP('localhost')
                s.sendmail(me, you, msg.as_string())
                s.quit()
                return


if __name__ == '__main__':
        f = open('../config/config.json', )
        data = json.load(f)
        rep = Report('../report/report.html')
        repHost = Report('../report/reportHost.html')
        f.close()

        os.system('kinit -kt /var/cv/devopsint/creds/devopsint.kt devopsint@GS.COM')
        cookie = subprocess.run("curl -s -I -u : --negotiate https://authn.web.gs.com/desktopsso/Login | awk '/GSSSO/ {print substr($2,0,length($2)-1)}' ",check=True,shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,universal_newlines=True)
        cookie = cookie.stdout
        print("Cookie has been generated ",cookie)
        cookie = cookie[:-1]

        urlList = []
        prodUrlList = []
        hostList.clear()

        for i in data['config']:
                if i['TYPE'] == 'server':
                        newUrl = Server(i['NAME'], i['URL'], i['ENV'])
                elif i['TYPE'] == 'api':
                        newUrl = Api(i['NAME'], i['URL'], i['ENV'])
                elif i['TYPE'] == 'process':
                        newUrl = Process(i['NAME'], i['URL'], i['ENV'])
                elif i['TYPE'] == 'multiHost':
                        newUrl = MultiHost(i['NAME'], i['URL'], i['ENV'], cookie, repHost)
                urlList.append(newUrl)

        firstRun = True
        timer = 0
        counter = 0
        while True:
                if(counter == 144) :
                        cookie = subprocess.run("curl -s -I -u : --negotiate https://authn.web.gs.com/desktopsso/Login | awk '/GSSSO/ {print substr($2,0,length($2)-1)}' ",check=True,shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,universal_newlines=True)
                        cookie = cookie.stdout
                        print("Cookie has been generated ",cookie)
                        cookie = cookie[:-1]
                        # update the cookie value for all the multihost objects
                        for i in urlList:
                                if(isinstance(i,MultiHost)):
                                        i.cookie = cookie

                rep.flush()
                repHost.flush()
                rep.emailSummary = ""
                currentEnv = "DNE"
                timer += 1
                for i in urlList:
                        if currentEnv != i.env:
                                if i.env == 'BETA' or i.env == 'UAT':
                                        repHost.summary += ('<th class="env-head %s " colspan = "3">%s</th>' % (i.env, i.env))
                                currentEnv = i.env
                                rep.summary += ('<th class="env-head %s " colspan = "3">%s</th>' % (i.env, i.env))
                                rep.emailSummary += ('</tbody></table>')
                                rep.emailSummary += ('<h1 style="color:black">%s</h1>' %( i.env))
                                rep.emailSummary += ('<table style="border:1px solid; table-layout: fixed; width: 400px"><thead <th style="border: 1px solid; width: 200px; overflow: hidden;">Service</th><th style="border: 1px solid; width: 100px; overflow: hidden;">Status</th></thead><tbody>')

                        if i.ping(firstRun):
                                logging.debug("[%s] %s :: Success" % (i.env, i.name))
                        else:
                                logging.error("[%s] %s :: Error accessing URL" % (i.env, i.name))
                        rep.append(i)

                # To send the mail to the leads every 4 hours
                currentTime = datetime.datetime.now()
                currentTimeString = currentTime.strftime("%H:%M")
                expectedTimeBefore = ["23:27", "03:27", "07:27", "11:27", "15:27", "19:27"]
                expectedTimeAfter = ["23:34", "03:33", "07:33", "11:33", "15:33", "19:33"]
                for (b,f) in zip(expectedTimeBefore, expectedTimeAfter):
                        if currentTimeString > b and currentTimeString < f and (rep.intHealth==1 or rep.qaHealth==1 or rep.uatHealth==1 or rep.betaHealth ==1):
                                timer = 0

                                me = "gs-am-it-digital-sma-devops@internal.email.gs.com"
                                you = ["gs-amd-digital-squad-leads@internal.email.gs.com", "gs-am-it-digital-sma-devops@internal.email.gs.com"]
                                # Creating message container - the correct MIME type is multipart/alternative.
                                msg = MIMEMultipart('alternative')
                                msg['Subject'] = "Scheduled Health Report for all NON PROD Services"
                                msg['From'] = me
                                msg['To'] = ", ".join(you)
                                emailText = rep.emailHeader + rep.emailSummary + rep.emailFooter
                                part = MIMEText(emailText, 'html')
                                msg.attach(part)
                                s = smtplib.SMTP('localhost')
                                s.sendmail(me, you, msg.as_string())
                                s.quit()

                if rep.intHealth == 1:
                        rep.sendMail("INT")
                        rep.intHealth = 0
                if rep.qaHealth == 1:
                        rep.sendMail("QA")
                        rep.qaHealth = 0
                if rep.uatHealth == 1:
                        rep.sendMail("UAT")
                        rep.uatHealth = 0
                if rep.betaHealth == 1:
                        rep.sendMail("BETA")
                        rep.betaHealth = 0
                # regenerate HTML report
                rep.print()
                repHost.print()
                logging.debug('Report Host ',str(repHost.summary))
                time.sleep(300)
                counter += 1
                firstRun = False
