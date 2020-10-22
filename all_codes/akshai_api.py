#!flask/bin/python
from flask import Flask, jsonify, request
import urllib.request
import os
import time, sys
import inspect
from os import environ as env

from  novaclient import client
import keystoneclient.v3.client as ksclient
from keystoneauth1 import loading
from keystoneauth1 import session

app = Flask(__name__)



loader = loading.get_plugin_loader('password')

auth = loader.load_from_options(auth_url=env['OS_AUTH_URL'],
                                    username=env['OS_USERNAME'],
                                    password=env['OS_PASSWORD'],
                                    project_name=env['OS_PROJECT_NAME'],
                                    project_domain_name=env['OS_USER_DOMAIN_NAME'],
                                    project_id=env['OS_PROJECT_ID'],
                                    user_domain_name=env['OS_USER_DOMAIN_NAME'])

sess = session.Session(auth=auth)
nova = client.Client('2.1', session=sess)

worker_name = "akshai_worker"

#1Uw93BSs1DSXu8SQeQH4FWraV1ZilgEr9
#curl  http://130.238.29.19:5000/upload_url/<google_drive_fileid>/<filename>/<folder_name>
@app.route('/upload_url/<file_id>/<filename>/<path:folder_name>', methods=['GET'])
def upload_url(file_id,filename,folder_name):
    
    url = "https://docs.google.com/uc?export=download&id=" + file_id
    
    os.system (" hdfs dfs -ls  /" + folder_name + " 2>&1 | tee hdfs.log")
    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            os.system("hdfs dfs -mkdir /" + folder_name + " 2>&1 | tee hdfs.log")
            
        if file_read.find(filename) != -1:
            return ("File already exists")

            
    os.system("wget --no-check-certificate '" + url + "' -O - | hdfs dfs -put - /" + folder_name + "/" + filename)
    
    
    return ("Success")



#curl -i -X POST http://130.238.29.19:5000/upload_file -F 'file=@20417.txt.utf-8' -F folder_name=
@app.route('/upload_file', methods=['POST'])
def upload_file():
    
    folder_name = (request.form["folder_name"])

    filename = str(request.files["file"].filename)

    with open('tmp_file.txt', 'wb') as f:
        f.write(request.data)
    
    os.system (" hdfs dfs -put tmp_file.txt " + folder_name + filename + " 2>&1 | tee hdfs.log")
    
    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("File exists") != -1:
            return ("File already exists")
        
        if file_read.find("No such file or directory") != -1:
            os.system("hdfs dfs -mkdir " + folder_name + " 2>&1 | tee hdfs.log")
            os.system ("hdfs dfs -put tmp_file.txt " + folder_name + filename + " 2>&1 | tee hdfs.log")
            
    os.system("rm tmp_file.txt")
    return ("Success")


#curl  http://130.238.29.19:5000/delete_file/<filename>/<folder_name>
@app.route('/delete_file/<filename>/<path:folder_name>', methods=['GET'])
def delete_file(filename,folder_name):
    
    os.system (" hdfs dfs -ls  /" + folder_name + " 2>&1 | tee hdfs.log")
    
    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            return ("Folder name does not exists")
        
        if file_read.find(filename) == -1:
            return ("Filename does not exists")
            
    os.system (" hdfs dfs -rm /" + folder_name + "/" + filename)
        
    return ("Success")


#curl  http://130.238.29.19:5000/delete_folder/<folder_name>
@app.route('/delete_folder/<path:folder_name>', methods=['GET'])
def delete_folder(folder_name):
    
    os.system ("hdfs dfs -ls  /" + folder_name + " 2>&1 | tee hdfs.log")

    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            return ("Folder name does not exists")
            
    os.system ("hdfs dfs -rm -r  /" + folder_name)
        
    return ("Success")


def edit_host_file(vm_name,filename):
    with open(filename,"r") as f:
        open_file = f.readlines()
        
        output_entry = ""
        for line in open_file:
            if vm_name not in line:
                output_entry += line
        
        output_file = open(filename,"w")
        output_file.write(output_entry)


@app.route('/delete_node/<string:fixed_ip>', methods=['GET'])
def delete_node(fixed_ip):
    
    servers = nova.servers.list()
    
    for i in servers:
        if list(i.addresses.values())[0][0]["addr"] == fixed_ip:
            nova.servers.delete(i.id)
            
            os.system('ssh-keygen -f "/home/akshai/.ssh/known_hosts" -R "' + fixed_ip + '"')
            
            edit_host_file(i.name,"/etc/ansible/hosts")
            print ("Edited /etc/ansible/hosts")
            
            edit_host_file(i.name,"/etc/hosts")
            print ("Edited /etc/hosts")
            
            #run_ansible_delete_node()
            #print ("Ansible reran for the current nodes")
            
            return ("VM with ID :" + str(i.id) + " deleted")
    
    return ("Could not find the VM with IP " + fixed_ip)

    
def run_ansible_new_node(vm_name):
    while True:
        if os.system('ansible-playbook spark_deployment_new_node_test_file.yml -b --extra-vars "target=' + vm_name + '"') == 0:
            return (True)
        else:
            time.sleep(5)
            print ("Trying again for ansible installation")
            


@app.route('/add_another_node/<int:count>', methods=['GET'])
def add_another_node(count):
    
    master_public_key = open("/home/ubuntu/.ssh/id_rsa.pub","r").read()[:-1]
    
    if master_public_key not in open("cloud-cfg2.txt","r").read():
        cloud_init_output = open("cloud-cfg2.txt","a")
        cloud_init_output.write(' - sudo echo "' + master_public_key + '" >> /home/ubuntu/.ssh/authorized_keys')
        cloud_init_output.close()
    
    # Find current count of workers
    current_vm_count = 0
    servers = nova.servers.list()
    for i in servers:
        if worker_name in i.name:
            current_vm_count += 1
    
    # Deploying new vms
    new_ip_dict = {}
    for i in range(count):
        new_vm_name = worker_name + str(current_vm_count + 1 + i)
        os.system("python3 ssc-instance-userdata.py " + new_vm_name)
        new_ip_dict[new_vm_name] = ""
        
    
    servers = nova.servers.list()
    vm_names = ""
    for new_vm_name in list(new_ip_dict.keys()):
        for i in servers:
            if i.name == new_vm_name:
                new_ip_dict[new_vm_name] = (list(i.addresses.values())[0][0]["addr"])
                if len (list(new_ip_dict.keys())) > 1:
                    vm_names += new_vm_name + ","
                else:
                    vm_names += new_vm_name
    
    
    # Ansible IP entries
    initial_entry = ""
    final_entry = ""
    for vm in new_ip_dict:
        
        initial_entry += vm +  " ansible_ssh_host=" + new_ip_dict[vm] + "\n"
        final_entry += vm + " ansible_connection=ssh ansible_user=ubuntu ansible_ssh_extra_args='-o StrictHostKeyChecking=no'\n"
        
        os.system('echo "' + new_ip_dict[vm]  + ' ' + vm+ '" >> /etc/hosts')
        
    with open("/etc/ansible/hosts","r") as f:
        open_file = f.read()
        output_open = open("/etc/ansible/hosts","w")
        output = initial_entry + open_file + final_entry 
        output_open.write(output)
        output_open.close()
    
    
    
    run_ansible_new_node(vm_names)
    
    return ("Success")

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
