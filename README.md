# monitoring Dashboard

A python utility to constantly poll the health and status of micro-service endpoints and present a html report

### Conduit structure:
This conduit project performs below actions:
* Provides required hardware
* deploys Python script and config files on target host
* Runs the Python script
* Runs a python http server to host the html report

Dev URL: http://example.com:8000/report.html

### How to read the report
![sample-report-image](report-page.jpg)

* (1) Time at which the report was generated. Gets refreshed every five minutes.(configurable)
* (2) Each row represents a service and its status for past four hours. Each colored square represents a 5 min block
* (3) Swagger link of the service
* (4) Availability percentage of the service during the monitoring period
* (5) Sample representation of failures

#### color coding of the report
- Green - All Good. Able to ping the service
- Amber - Service down
- Grey - Unable to test. Some other issues
- Red Underline on the box - represents a version change on the microservice compared to previous ping
