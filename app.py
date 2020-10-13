from flask import Flask 
from novaclient import client 
from keystoneauth1 import loading, session
import os 
from os import environ as env 

app = Flask(__name__)

loader = loading.get_plugin_loader("password")
auth = loader.load_from_options(auth_url=env['OS_AUTH_URL'], 
                                username=env['OS_USERNAME'], 
                                password=env['OS_PASSWORD'],
                                project_id=env['OS_PROJECT_ID'], 
                                user_domain_name=env["OS_USER_DOMAIN_NAME"], 
                                project_domain_name=env["OS_PROJECT_DOMAIN_ID"])

sess = session.Session(auth=auth)
nova = client.Client("2", session=sess)

@app.route("/delete", methods=["GET"])
def delete(): 
    currentVMS = nova.servers.list()
    print(currentVMS)
    for x in currentVMS: 
        if "kev-decom" in x.name.lower(): 
            print("Found the Kevin VM!")
            print(x)
            print("Deleting " + x.name + " VM now....")
            nova.servers.delete(x)

    # Just to have some html displayed
    return "Hello world!"

@app.route("/delete/<vmName>", methods=["GET"])
def deleteWorker(vmName): 
    currentVMS = nova.servers.list()
    for x in currentVMS: 
        if vmName in x.name.lower(): 
            print("Found the VM you searched for!")
            print("Found the VM: " + x.name)
            print("You searched for the VM: " + vmName)
            nova.servers.delete(x)
    
    return "The VM you searched for is " + vmName






if __name__ == "__main__": 
    app.run(host="0.0.0.0", debug=True)