import os
from novaclient import client
from keystoneauth1 import loading
from keystoneauth1 import session




def generate_ssh_keypair():
    os.system("ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa -y")
    os.system("cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys")
    os.system("chmod 0600 ~/.ssh/authorized_keys")


def edit_cloud_config(filename,master=None):
    master_public_key = open("/home/ubuntu/.ssh/id_rsa.pub","r").read()[:-1]
    
    with open(filename,"r") as f:
        read_lines = f.readlines()
        output_write = ""
        for line in read_lines:
            if "/home/ubuntu/.ssh" not in line:
                output_write += line
        output_write += ' - sudo echo "' + master_public_key + '" >> /home/ubuntu/.ssh/authorized_keys\n'
        
        if master == "ansible":
            master_private_key = open("/home/ubuntu/.ssh/id_rsa","r").readlines()
            for line in master_private_key:
                output_write += ' - sudo echo "' + line[:-1] + '" >> /home/ubuntu/.ssh/id_rsa\n'
            
        
        cloud_init_output = open(filename,"w")
        cloud_init_output.write(output_write)
        cloud_init_output.close()
