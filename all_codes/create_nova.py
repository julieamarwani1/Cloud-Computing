import time, sys
from novaclient import client
from keystoneauth1 import loading
from keystoneauth1 import session
from util import create_and_validate_cfg_dict, get_credentials

def create():
    nodes = ['ansible-master', 'spark-master', 'spark-worker']

    flavor = "ssc.medium"
    private_net = 'UPPMAX 2020/1-2 Internal IPv4 Network'
    floating_ip_pool_name = None
    floating_ip = None
    image_name = 'Ubuntu 18.04'
    security_groups = {node: ['default', f"{node}-group"] for node in nodes}
    userdata_dict = create_and_validate_cfg_dict(nodes)

    loader = loading.get_plugin_loader('password')

    credentials = get_credentials()
    auth = loader.load_from_options(**credentials)

    sess = session.Session(auth=auth)
    nova = client.Client('2.1', session=sess)
    print("user authorization completed.")

    image = nova.glance.find_image(image_name)

    flavor = nova.flavors.find(name=flavor)

    if private_net is not None:
        net = nova.neutron.find_network(private_net)
        nics = [{'net-id': net.id}]
    else:
        print("private-net not defined.")
        return False

    for node in nodes:
        print("Creating instance ... ")
        instance = nova.servers.create(name=node, key_name='a2', image=image, flavor=flavor, userdata=userdata_dict[node], nics=nics,
            security_groups=security_groups[node])
        inst_status = instance.status
        print("waiting for 10 seconds.. ")
        time.sleep(10)
        while inst_status == 'BUILD':
            print("Instance: " + instance.name + " is in " + inst_status + " state, sleeping for 5 seconds more...")
            time.sleep(5)
            instance = nova.servers.get(instance.id)
            inst_status = instance.status
    
        print("Instance: " + instance.name + " is in " + inst_status + "state")
    return True
