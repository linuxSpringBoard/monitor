from http.server import HTTPServer, BaseHTTPRequestHandler
import ssl
import os
import logging
logging.basicConfig(level=logging.DEBUG)  

LOGGER = logging.getLogger(__name__)  

def startSession():
    os.chdir('/local/scratch/ecg-dashboard/report') 
    httpd = HTTPServer(('example.com', 80), SimpleHTTPRequestHandler) 
    httpd.socket = ssl.wrap_socket (httpd.socket, 
        keyfile="/var/creds/1.key", 
        certfile='/var/creds/1.cer', server_side=True)

    httpd.serve_forever()

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            file_to_open = open(os.getcwd()+"/"+self.path[1:]).read()
            LOGGER.info(str(file_to_open))
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes(file_to_open,'utf-8'))            
        except Exception as e:
            LOGGER.error(str(e))
            file_to_open = "File Not Found"
            self.send_response(400)        

if __name__ == '__main__':
    startSession()
