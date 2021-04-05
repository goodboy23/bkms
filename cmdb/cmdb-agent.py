#!/usr/bin/python
# -*- coding: utf-8 -*-  



import json, os, sys,  commands
import subprocess, time, platform
from socket import *
import socket, logging

#[master地址、端口]
MASTER_IP = '10.0.0.1'
MASTER_PORT = 9527

class SystemInfo():
    """获取系统信息"""

    def __init__(self):
        logging.basicConfig(level=logging.INFO,
            format='%(asctime)s %(funcName)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %A %H:%M:%S')
        self.logging = logging

    def get_name(self):
        """获取当前机器主机名"""

        return socket.gethostname()

    def get_mem(self):
        """获取主机内存，单位M"""

        with open("/proc/meminfo") as f:
            tmp = int(f.readline().split()[1])
            return tmp / 1000

    def get_swap(self):
        """获取SWAP，单位M"""

        swap_number = 0
        if len(open("/proc/swaps", 'r').readlines()) != 1:
            with open("/proc/swaps") as f:
                for line in f:
                    tmp = line.split()
                    if len(tmp) == 5 and tmp[2].isdigit() is True:
                        swap_number += int(tmp[2]) / 1024
            return swap_number
        else:
            return 0
  
    def get_ker(self):
        """获取内核与架构

        return:
            ker_dict = {'kernel': '3.10.0-514.26.2.el7', 'framework': 'x86_64'}
        """
        
        with open("/proc/version") as f:
            ker_dict = {}
            tmp = f.readline().split()[2]
            tmp_list = tmp.split('.')
            framework = tmp_list.pop()
            kernel = '.'.join(tmp_list)
            ker_dict['kernel'] = kernel
            ker_dict['framework'] = framework

        return ker_dict

    def get_cpu(self):
        """返回的是核心数和型号的字典

        return 
            cpu_info_dict= { "cpu_model": "Intel(R) Xeon(R) Platinum 8163 CPU @ 2.50GHz",'cpu_number':6}
        """

        cpu_info_dict = {'cpu_model':'','cpu_number':0}
        with open('/proc/cpuinfo') as f:
            for line in f:
                tmp = line.split(":")
                key = tmp[0].strip()
                if key == "processor":
                    cpu_info_dict['cpu_number'] += 1
                if key == "model name":
                    cpu_info_dict['cpu_model'] = tmp[1].strip()
        return cpu_info_dict

    def get_disk(self, key):
        """获取主机磁盘总容量，单位G"""
        disk_number = 0
        with open("/proc/partitions") as f:
            for line in f:
                tmp = line.split()
                if len(tmp) == 4:
                    if tmp[2].isdigit() is True and tmp[3].isalpha() is True:
                        disk_number += int(tmp[2]) / 1024 / 1024
        return disk_number

    def get_manufacturer(self):
        """返回制造商信息

        return:
            manufacturer = "Lenovo ThinkSystem SR550 -[7X04CTO1WW]-/-[7X04CTO1WW]-"
        """

        with open("/var/log/dmesg") as f:
            for line in f:
                if "DMI:" in line:
                    tmp = line.split("DMI: ")
                    tmp = tmp[1].split(",")
                    return tmp[0]

    def get_version(self):
        """获取版本，CentOS Linux 7.3.1611 Core"""

        return ' '.join(platform.linux_distribution())

def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

#向master程序提交信息
def post_port(data):
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.connect((MASTER_IP,MASTER_PORT))

    data['host_ip'] = get_host_ip()
    data = str(data)
    s.send(data.encode('utf-8'))
    s.close()

if __name__ == '__main__':
    host_info_dict = {}

    host_inst = SystemInfo()
    host_info_dict["bk_host_name"] = host_inst.get_name()
    host_info_dict["bk_mem"] = host_inst.get_mem()
    host_info_dict["bk_swap"] = host_inst.get_swap()

    ker_dict = host_inst.get_ker()
    host_info_dict["bk_ker"] = ker_dict["kernel"]
    host_info_dict["bk_os_bit"] = ker_dict['framework']

    cpu_info_dict =  host_inst.get_cpu()
    host_info_dict["bk_cpu_module"] = cpu_info_dict["cpu_model"]
    host_info_dict["bk_cpu"] = cpu_info_dict["cpu_number"]
    try:
        host_info_dict["bk_disk"] = host_inst.get_disk("Disk")
    except:
        host_info_dict["bk_disk"] = host_inst.get_disk("磁盘")

    host_info_dict["bk_manufacturers"] = host_inst.get_manufacturer()
    host_info_dict["bk_os_name"] = host_inst.get_version()
   
    post_port(host_info_dict)
    print("更新信息完成")
