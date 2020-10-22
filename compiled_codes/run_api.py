#!flask/bin/python
import time, sys
from novaclient import client
from keystoneauth1 import loading
from keystoneauth1 import session
from flask import Flask, jsonify, request
import urllib.request
import os
import inspect
from os import environ as env
import keystoneclient.v3.client as ksclient


# Custom file
import supp_file as sf

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

worker_name = "G1_worker"
ansible_master = "G1_ansible-master"
spark_master = 'G1_spark-master'
keypair="openstackssh"

@app.route("/decommission", methods=["GET"])
def decommission(): 
    currentVMS = nova.servers.list()
    print(currentVMS)
    for vm in currentVMS: 
        if worker_name in vm.name or ansible_master in vm.name or spark_master in vm.name: 
            print("Found the VM!" + vm.name)
            print("Deleting " + vm.name + " VM now....")
            nova.servers.delete(vm)

    return "All VMs are deleted\n"

def create_vm(vm_name,flavor,keypair,user_data):
    
    flavor = flavor
    private_net = 'UPPMAX 2020/1-2 Internal IPv4 Network'
    floating_ip_pool_name = None
    floating_ip = None
    image_name = 'Ubuntu 18.04'
    security_group = ['default'] # {node: ['default', f"{node}-group"] for node in nodes}
    #userdata_dict = create_and_validate_cfg_dict(nodes)

    image = nova.glance.find_image(image_name)

    flavor = nova.flavors.find(name=flavor)
    
    if private_net is not None:
        net = nova.neutron.find_network(private_net)
        nics = [{'net-id': net.id}]
    else:
        print("private-net not defined.")
        return False
    
    userdata = open(user_data)
    
    print("Creating instance ... ")
    instance = nova.servers.create(name=vm_name, key_name=keypair, image=image, flavor=flavor, userdata=userdata, nics=nics,
            security_groups=security_group)
    inst_status = instance.status
    print("waiting for 10 seconds.. ")
    time.sleep(10)
    while inst_status == 'BUILD':
        print("Instance: " + instance.name + " is in " + inst_status + " state, sleeping for 5 seconds more...")
        time.sleep(5)
        instance = nova.servers.get(instance.id)
        inst_status = instance.status
    
    print("Instance: " + instance.name + " is in " + inst_status + "state")
    
    servers = nova.servers.list()
    for i in servers:
        if vm_name in i.name:
            vm_ip = (list(i.addresses.values())[0][0]["addr"])
            
    return vm_ip


@app.route('/create/<string:flavour>', methods=['GET'])
def create(flavour):
    
    cloud_config_path = os.getcwd() + "/configs/cloud_cfg.txt"
    ansible_cloud_config_path = os.getcwd() + "/configs/cloud_ansible_cfg.txt"
    
    sf.edit_cloud_config(ansible_cloud_config_path,"ansible")
    sf.edit_cloud_config(cloud_config_path)


    ansible_ip = create_vm(ansible_master,flavour,keypair,ansible_cloud_config_path)
    
    spark_master_ip = create_vm(spark_master,flavour,keypair,cloud_config_path)
    worker_ip = create_vm(worker_name,flavour,keypair,cloud_config_path)
    
    
    ansible_hosts_output = ansible_master + " ansible_ssh_host=" + ansible_ip + "\n"
    ansible_hosts_output += spark_master + " ansible_ssh_host=" + spark_master_ip + "\n"
    ansible_hosts_output += worker_name + " ansible_ssh_host=" + worker_ip + "\n\n\n"
    ansible_hosts_output += "[configNode]\n" + ansible_master + " ansible_connection=local ansible_user=ubuntu\n\n"
    ansible_hosts_output += "[sparkmaster]\n" + spark_master + " ansible_connection=ssh ansible_user=ubuntu ansible_ssh_extra_args='-o StrictHostKeyChecking=no'\n\n"
    ansible_hosts_output += "[sparkworker]\n" + worker_name + " ansible_connection=ssh ansible_user=ubuntu ansible_ssh_extra_args='-o StrictHostKeyChecking=no'\n"
    
    ansible_file = open(os.getcwd() + "/configs/ansible_hosts","w")
    ansible_file.write(ansible_hosts_output)
    ansible_file.close()
    
    hosts_output = ansible_ip + " " + ansible_master + "\n"
    hosts_output += spark_master_ip + " " + spark_master + "\n"
    hosts_output += worker_ip + " " + worker_name + "\n\n\n"
    hosts_output += "# The following lines are desirable for IPv6 capable hosts" + "\n"
    hosts_output += "::1 ip6-localhost ip6-loopback" + "\n"
    hosts_output += "fe00::0 ip6-localnet" + "\n"
    hosts_output += "ff00::0 ip6-mcastprefix" + "\n"
    hosts_output += "ff02::1 ip6-allnodes" + "\n"
    hosts_output += "ff02::2 ip6-allrouters" + "\n"
    hosts_output += "ff02::3 ip6-allhosts" + "\n"
    
    hosts_file = open(os.getcwd() + "/configs/hosts","w")
    hosts_file.write(hosts_output)
    hosts_file.close()
    
    copy_files(ansible_ip)
    
    # Copying spark files
    os.system("scp " + os.getcwd() + "/configs/spark_deployment.yml" + " ubuntu@" + ansible_ip + ":~/spark_deployment.yml")
    os.system("scp " + os.getcwd() + "/configs/setup_var.yml" + " ubuntu@" + ansible_ip + ":~/setup_var.yml")
    os.system("scp " + os.getcwd() + "/configs/spark_deployment_new_node_test_file.yml" + " ubuntu@" + ansible_ip + ":~/spark_deployment_new_node_test_file.yml")
    os.system("scp " + os.getcwd() + "/configs/spark_deployment_new_node.yml" + " ubuntu@" + ansible_ip + ":~/spark_deployment_new_node.yml")
    #os.system("scp " + os.getcwd() + "/configs/spark_deployment_after_deletion.yml" + " ubuntu@" + ansible_ip + ":~/spark_deployment_after_deletion.yml")
    
    os.system('ssh ubuntu@' + ansible_ip + ' "ansible-playbook -b ~/spark_deployment.yml"')
    
    return "VMs created\n"
    
def copy_files(ansible_ip):
    while True:
        if os.system("ssh -o StrictHostKeyChecking=no ubuntu@" + ansible_ip + "  'ls'") == 0:
            os.system("scp " + os.getcwd() + "/configs/ansible_hosts" + " ubuntu@" + ansible_ip + ":~/ansible_hosts")
            os.system('ssh ubuntu@' + ansible_ip + ' "sudo mv ~/ansible_hosts /etc/ansible/hosts"')
            
            os.system("scp " + os.getcwd() + "/configs/hosts" + " ubuntu@" + ansible_ip + ":~/hosts")
            os.system('ssh ubuntu@' + ansible_ip + ' "sudo mv ~/hosts /etc/hosts"')
            
            os.system('ssh ubuntu@' + ansible_ip + ' "chmod 777 /etc/ansible/hosts"')
            os.system('ssh ubuntu@' + ansible_ip + ' "chmod 777 /etc/hosts"')
            break
        time.sleep(5)
    
    return True
 
#1Uw93BSs1DSXu8SQeQH4FWraV1ZilgEr9
#curl  http://130.238.29.19:5000/upload_url/<google_drive_fileid>/<filename>/<folder_name>
@app.route('/upload_url/<file_id>/<filename>', methods=['GET'])
@app.route('/upload_url/<file_id>/<filename>/<path:folder_name>', methods=['GET'])
def upload_url(file_id,filename,folder_name = ""):
    
    spark_ip = find_spark_master_ip()
            
    url = "https://docs.google.com/uc?export=download&id=" + file_id
    
    os.system ('ssh ubuntu@' + spark_ip + ' " ls  ~/' + folder_name + '" 2>&1 | tee folder.log')
    with open("folder.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            os.system('ssh ubuntu@' + spark_ip + ' " mkdir  ~/' + folder_name + '" 2>&1 | tee folder.log')
            
        if file_read.find(filename) != -1:
            return ("File already exists\n")

    print ('ssh ubuntu@' + spark_ip + ' "wget  --no-check-certificate \'' + url + '\' -O ~/' + folder_name + '/' + filename + '"')
    os.system('ssh ubuntu@' + spark_ip + ' "wget  --no-check-certificate \'' + url + '\' -O ~/' + folder_name + '/' + filename + '"')
    
    
    return ("Success\n")

@app.route('/file_check/<filename>/<path:folder_name>', methods=['GET'])
def file_check(filename,folder_name):
    
    spark_ip = find_spark_master_ip()
    os.system ('ssh ubuntu@' + spark_ip + ' " head  ~/' + folder_name + '/' + filename + '" 2>&1 | tee folder.log')
    print ('ssh ubuntu@' + spark_ip + ' " tail  ~/' + folder_name + '/' + filename + '"')
    return (str(open("folder.log","r").read()))


#curl -i -X POST http://130.238.29.19:5000/upload_file -F 'file=@20417.txt.utf-8' -F folder_name=
@app.route('/upload_file', methods=['POST'])
def upload_file():
    
    spark_ip = find_spark_master_ip()
    
    folder_name = (request.form["folder_name"])

    filename = str(request.files["file"].filename)

    with open(os.getcwd() + '/tmp_file.txt', 'wb') as f:
        f.write(request.files["file"].read())
    
    os.system ('ssh ubuntu@' + spark_ip + ' " ls  ~/' + folder_name + '" 2>&1 | tee folder.log')
    
    with open("folder.log","r") as f:
        file_read = f.read()
        
        if file_read.find("File exists") != -1:
            return ("File already exists\n")
        
        if file_read.find("No such file or directory") != -1:
            os.system('ssh ubuntu@' + spark_ip + ' " mkdir  ~/' + folder_name + '" 2>&1 | tee folder.log')
            os.system("scp " + os.getcwd() + "/tmp_file.txt " + " ubuntu@" + spark_ip + ":~/" + folder_name + "/" + filename)
        else:
            os.system("scp " + os.getcwd() + "/tmp_file.txt " + " ubuntu@" + spark_ip + ":~/" + folder_name + "/" + filename)
            
    os.system("rm " + os.getcwd() + "/tmp_file.txt")
    return ("Success\n")


#curl  http://130.238.29.19:5000/delete_file/<filename>/<folder_name>
@app.route('/delete_file/<filename>', methods=['GET'])
@app.route('/delete_file/<filename>/<path:folder_name>', methods=['GET'])
def delete_file(filename,folder_name = ""):
    
    spark_ip = find_spark_master_ip()
    
    os.system ('ssh ubuntu@' + spark_ip + ' " ls  ~/' + folder_name + '" 2>&1 | tee folder.log')
    
    with open("folder.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            return ("Folder name does not exists\n")
        
        if file_read.find(filename) == -1:
            return ("Filename does not exists\n")
            
    os.system ('ssh ubuntu@' + spark_ip + ' " rm  ~/' + folder_name + '/' + filename + '"' )
        
    return ("deleted file = " + filename + "\n\n\n The folder contains\n\n" + list_files(folder_name))


#curl  http://130.238.29.19:5000/delete_folder/<folder_name>
@app.route('/delete_folder/<path:folder_name>', methods=['GET'])
def delete_folder(folder_name):
    
    spark_ip = find_spark_master_ip()
    
    os.system ('ssh ubuntu@' + spark_ip + ' " ls  ~/' + folder_name + '" 2>&1 | tee folder.log')

    with open("folder.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            return ("Folder name does not exists\n")
            
    os.system ('ssh ubuntu@' + spark_ip + ' " rm -r ~/' + folder_name + '"' )
        
    return ("Deleted folder = " + folder_name + "\n")

@app.route('/list_files', methods=['GET'])
@app.route('/list_files/<path:folder_name>', methods=['GET'])
def list_files(folder_name = ""):
    
    spark_ip = find_spark_master_ip()
    
    os.system ('ssh ubuntu@' + spark_ip + ' " ls  ~/' + folder_name + '" 2>&1 | tee folder.log')

    with open("folder.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            return ("Folder name does not exists\n")
            
    os.system ('ssh ubuntu@' + spark_ip + ' " ls ~/' + folder_name + '" 2>&1 | tee folder.log' )
        
    return (str(open("folder.log","r").read()))


def find_spark_master_ip():
    servers = nova.servers.list()
    for i in servers:
        if i.name == spark_master:
            spark_ip = (list(i.addresses.values())[0][0]["addr"])
    
    return (spark_ip)
    
# Removing vm information after deleting the vm from hosts files
def edit_host_file(vm_name,filename):
    with open(filename,"r") as f:
        open_file = f.readlines()
        
        output_entry = ""
        for line in open_file:
            if vm_name not in line:
                output_entry += line
        
        output_file = open(filename,"w")
        output_file.write(output_entry)


@app.route('/deleteip/<string:fixed_ip>', methods=['GET'])
def deleteip(fixed_ip):
    
    servers = nova.servers.list()
    for i in servers:
        if i.name == ansible_master:
            ansible_ip = (list(i.addresses.values())[0][0]["addr"])
            
    for i in servers:
        if list(i.addresses.values())[0][0]["addr"] == fixed_ip:
            nova.servers.delete(i.id)
            
            os.system('ssh-keygen -f "/home/akshai/.ssh/known_hosts" -R "' + fixed_ip + '"')
            
            edit_host_file(i.name,os.getcwd() + "/configs/hosts")
            print ("Edited /etc/ansible/hosts")
            
            edit_host_file(i.name,os.getcwd() + "/configs/ansible_hosts")
            print ("Edited /etc/hosts")
            
            copy_files(ansible_ip)
            
            return ("VM with ID :" + str(i.id) + " deleted\n")
    
    return ("Could not find the VM with IP " + fixed_ip + "\n")

@app.route("/deletename/<string:vmName>", methods=["GET"])
def deletename(vmName): 
    servers = nova.servers.list()
    
    servers = nova.servers.list()
    for i in servers:
        if i.name == ansible_master:
            ansible_ip = (list(i.addresses.values())[0][0]["addr"])
    
    for i in servers: 
        if vmName == i.name: 
            print("Found the VM you searched for!")
            print("Found the VM: " + i.name)
            print("You searched for the VM: " + vmName)            
            nova.servers.delete(i)
            
            edit_host_file(i.name,os.getcwd() + "/configs/hosts")
            print ("Edited /etc/ansible/hosts")
            
            edit_host_file(i.name,os.getcwd() + "/configs/ansible_hosts")
            print ("Edited /etc/hosts")
            
            copy_files(ansible_ip)
            
            return "VM name  " + vmName + " is deleted \n"
        
    return "specified " + vmName + " is not found\n"

    
def run_ansible_new_node(vm_name,ansible_ip):
    while True:
        if os.system('ssh -o StrictHostKeyChecking=no ubuntu@' + ansible_ip  + ' "ansible-playbook spark_deployment_new_node.yml -b --extra-vars \'target=' + vm_name + '\'"') == 0:
            return ("Ansible finished executing\n")
        else:
            time.sleep(5)
            print ("Trying again for ansible installation")


@app.route('/add_another_node/<int:count>/<string:flavour>', methods=['GET'])
def add_another_node(count,flavour):
    
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
        create_vm(new_vm_name,flavour,keypair,os.getcwd() + "/configs/cloud_cfg.txt")
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
            if i.name == ansible_master:
                ansible_ip = (list(i.addresses.values())[0][0]["addr"])
    
    host_file = open(os.getcwd() + "/configs/hosts","a")
    
    # Ansible IP entries
    initial_entry = ""
    final_entry = ""
    for vm in new_ip_dict:
        
        initial_entry += vm +  " ansible_ssh_host=" + new_ip_dict[vm] + "\n"
        final_entry += vm + " ansible_connection=ssh ansible_user=ubuntu ansible_ssh_extra_args='-o StrictHostKeyChecking=no'\n"
        
        host_file.write(new_ip_dict[vm]  + ' ' + vm + "\n")
        
    with open(os.getcwd() + "/configs/ansible_hosts","r") as f:
        open_file = f.read()
        output_open = open(os.getcwd() + "/configs/ansible_hosts","w")
        output = initial_entry + open_file + final_entry 
        output_open.write(output)
        output_open.close()
    
    copy_files(ansible_ip)
    
    run_ansible_new_node(vm_names,ansible_ip)
    
    return ("Success\n")

@app.route('/listnodes', methods=['GET'])
def listnodes():
    
    servers = nova.servers.list()
    output_list = "VM_name\t\t    IP_address\n"
    for i in servers:
        if worker_name in i.name or ansible_master in i.name or spark_master in i.name:
            output_list += i.name + "\t    " + list(i.addresses.values())[0][0]["addr"] + "\n"
    
    return (output_list)
            
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
