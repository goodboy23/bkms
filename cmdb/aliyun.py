from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException
import logging, configparser, json


class AliYun():
    """阿里云操作

    argvs:
        CONF_SITE: 配置文件所在的位置
    """

    def __init__(self,CONF_SITE):
        #日志
        logging.basicConfig(level=logging.INFO,
            format='%(asctime)s %(funcName)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %A %H:%M:%S')
        self.logging = logging

        #读取配置文件
        self.cfg = configparser.ConfigParser()
        self.cfg.read(CONF_SITE)

        #[ak、sk、所在地域、初始化]
        aliyun_user_ak = self.cfg['aliyun']['aliyun_user_ak']
        aliyun_user_sk = self.cfg['aliyun']['aliyun_user_sk']
        region_id = self.cfg['aliyun']['region_id']
        self.client = AcsClient(ak=aliyun_user_ak, secret=aliyun_user_sk, region_id=region_id, timeout=300)

        #阿里云中VPC的信息
        self.vpc_info_dict = {}

    def get_ecs_info(self, host_ip):
        """查询ECS信息

        argvs:
            host_ip = "1.1.1.1"

        return:
            ecs_info_dict = {
                "bk_create_time" = "None"
                "bk_ecs_name" = "None"
                "bk_bandwidth" = "0"
                "bk_aliyun_id" = "0"
                "vpc_id" = "None"
                "bk_type" = "1" //0云主机，1物理机
            }
        """

        from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest
        request = DescribeInstancesRequest()
        request.set_accept_format('json')
        request.set_InstanceNetworkType("vpc")
        request.set_PrivateIpAddresses([host_ip])
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        ecs_info_dict = {}
        if res_dict["Instances"]["Instance"]:
            ecs_info = res_dict["Instances"]["Instance"][0]
            ecs_info_dict["bk_create_time"] = ecs_info["CreationTime"]
            ecs_info_dict["bk_ecs_name"] = ecs_info["InstanceName"]
            if ecs_info['EipAddress']['IpAddress']:
                ecs_info_dict["bk_bandwidth"] = ecs_info['EipAddress']['IpAddress']
            else:
                ecs_info_dict["bk_bandwidth"] = "0"
            ecs_info_dict["bk_aliyun_id"] = ecs_info["InstanceId"]
            ecs_info_dict["bk_vpc"] = self.vpc_info_dict[ecs_info["VpcAttributes"]["VpcId"]]
            ecs_info_dict["bk_type"] = "0"

        else:
            ecs_info_dict["bk_create_time"] = "None"
            ecs_info_dict["bk_ecs_name"] = "None"
            ecs_info_dict["bk_bandwidth"] = "0"
            ecs_info_dict["bk_aliyun_id"] = "None"
            ecs_info_dict["bk_vpc"] = "None"
            ecs_info_dict["bk_type"] = "1"

        return ecs_info_dict
        
    def get_vpc(self):
        """获取VPC信息

        return:
            vpc_info_dict = {"vpc-bp1qpo0kug3a20qq": "生产环境VPC"}
        """

        from aliyunsdkvpc.request.v20160428.DescribeVpcsRequest import DescribeVpcsRequest
        request = DescribeVpcsRequest()
        request.set_accept_format('json')
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        vpc_info_dict = {}
        if res_dict["TotalCount"] != 0:
            for vpc_info in res_dict["Vpcs"]["Vpc"]:
                vpc_info_dict[vpc_info["VpcId"]] = vpc_info["VpcName"]

        return vpc_info_dict

    def get_dns_name(self):
        """获得该阿里云账号下的一级域名列表，只返回有记录的

        return:
            dns_name_list = ["xx.cn", "cc.cn"]
        """
        from aliyunsdkalidns.request.v20150109.DescribeDomainsRequest import DescribeDomainsRequest

        request = DescribeDomainsRequest()
        request.set_accept_format('json')
        request.set_PageSize("99")
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)
        
        #查看总是是不是大于0
        dns_name_list = []
        if res_dict["TotalCount"] > 0:
            for i in res_dict["Domains"]["Domain"]:
                dns_name_list.append(i["DomainName"])
        return dns_name_list

    def get_dns_recording(self, dns_name):
        """根据一级域名获取包含二级域名具体信息的列表

        argvs:
            dns_name = "xx.cn"

        return:
            dns_recording_list = [
                {
                    'RP':'www',  //值
                    'Status':'ENABLE', //解析状态，启动或禁用
                    'Type':'A', //解析类型
                    'Value':'1.1.1.1' //对应地址
                }
            ]
        """
        from aliyunsdkalidns.request.v20150109.DescribeDomainRecordsRequest import DescribeDomainRecordsRequest

        request = DescribeDomainRecordsRequest()
        request.set_accept_format('json')
        request.set_PageSize("499")
        request.set_DomainName(dns_name)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        #查看总数是不是大于0，有的域名没有记录
        if res_dict["TotalCount"] > 0:
            dns_recording_list = res_dict["DomainRecords"]["Record"]
            return dns_recording_list

    def get_slb_id(self):
        """获取当前账号下SLB的id号列表

        return:
            slb_id_list = ['lb-xxxxxxxxxxxxxxxx', 'lb-ccccccccccccc']
        """
        from aliyunsdkslb.request.v20140515.DescribeLoadBalancersRequest import DescribeLoadBalancersRequest

        request = DescribeLoadBalancersRequest()
        request.set_accept_format('json')
        request.set_PageSize(99)
        response = self.client.do_action_with_exception(request)

        #拿出id号
        slb_id_list = []
        res_dict = json.loads(response)
        for i in res_dict["LoadBalancers"]["LoadBalancer"]:
            slb_id_list.append(i["LoadBalancerId"])
        return slb_id_list

    def get_slb_recording(self, slb_id):
        """获取这个SLB实例的具体信息的字典
    
        argvs:
            slb_id = "lb-xxxxxxxxxxxxxxxx"

        return:
            slb_info_dict = {
                'bk_bandwidth': "5120", //带宽
                'bk_cost_type': '0', //付费方式
                'bk_inst_name': 'lb-xxxxxxxxxxxxxx', //slb的id号
                'bk_slb_name': '生产-会员-内网', //slb实例名称
                'bk_ip': '10.0.99.1', //slb的ip
                'bk_spec_type': '1', //slb规格类型
                'bk_port_dict': {'80': 'http'} //slb监听的端口和协议
            }
        """

        from aliyunsdkslb.request.v20140515.DescribeLoadBalancerAttributeRequest import DescribeLoadBalancerAttributeRequest
        request = DescribeLoadBalancerAttributeRequest()
        request.set_accept_format('json')
        request.set_LoadBalancerId(slb_id)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        slb_info_dict = {}
        slb_spec_dict = {"slb.s1.small":"1", "slb.s2.small":"2", "slb.s2.medium":"3", "slb.s3.small":"4", "slb.s3.medium":"5", "slb.s3.large":"6"}
        slb_info_dict["bk_bandwidth"] = str(res_dict["Bandwidth"])
        
        slb_info_dict["bk_inst_name"] = slb_id
        slb_info_dict["bk_slb_name"] = res_dict["LoadBalancerName"]
        slb_info_dict["bk_ip"] = res_dict["Address"]

        if  res_dict["InternetChargeType"] == "paybybandwidth":
            slb_info_dict["bk_cost_type"] = "0"
        else:
            slb_info_dict["bk_cost_type"] = "1"

        if res_dict["AddressType"] == "intranet":
            slb_info_dict["bk_net_type"] = "0"
        else:
            slb_info_dict["bk_net_type"] = "1"

        if "LoadBalancerSpec" in res_dict.keys():
            slb_info_dict["bk_spec_type"] = slb_spec_dict[res_dict["LoadBalancerSpec"]]
        else:
            slb_info_dict["bk_spec_type"] = "0"

        if res_dict["VpcId"]:
            slb_info_dict["bk_vpc"] = self.vpc_info_dict[res_dict["VpcId"]]
        else:
            slb_info_dict["bk_vpc"]  = "None"

        #一个SLB可能监听多个端口，这里要加上
        bk_port_dict = {}
        for i in res_dict["ListenerPortsAndProtocal"]["ListenerPortAndProtocal"]:
            bk_port_dict[str(i["ListenerPort"])] = i["ListenerProtocal"]
        slb_info_dict["bk_port_dict"] = bk_port_dict
        return slb_info_dict

    def get_slb_https(self, slb_id, slb_port):
        """查看SLB中httpS协议和端口所定义的虚拟服务器组

        argvs:
            slb_id = "lb-xxxxxxxxxxxxx"
            slb_port = 443

        return:
            slb_rsp_dict = {
                'all': 'rsp-2zexxxxxxxxxx', //默认的服务器组id，没有则为字符串None
                'www.xx.cn/rest': 'rsp-2zexxxxxxxxxxx' //域名+url和对应的服务器组id
            }
        """

        from aliyunsdkslb.request.v20140515.DescribeLoadBalancerHTTPSListenerAttributeRequest import DescribeLoadBalancerHTTPSListenerAttributeRequest
        request = DescribeLoadBalancerHTTPSListenerAttributeRequest()
        request.set_accept_format('json')
        request.set_ListenerPort(slb_port)
        request.set_LoadBalancerId(slb_id)
        response = self.client.do_action_with_exception(request)

        res_dict = json.loads(response)
        slb_rsp_dict = {}
        if "VServerGroupId" in res_dict.keys():
            slb_rsp_dict["all"] = res_dict["VServerGroupId"]
        else:
            slb_rsp_dict["all"] = "None"

        #不为空则加入到字典
        if len(res_dict["Rules"]["Rule"]) > 0:
            for i in res_dict["Rules"]["Rule"]:
                if "Url" in i.keys():
                    domain_url = i["Domain"] + i["Url"]
                    slb_rsp_dict[domain_url] = i["VServerGroupId"]
                else:
                    slb_rsp_dict[i["Domain"]] = i["VServerGroupId"]
        return slb_rsp_dict

    def get_slb_http(self, slb_id, slb_port):
        """查看SLB中http协议和端口所定义的虚拟服务器组

        argvs:
            slb_id = "lb-xxxxxxxxxxxxx"
            slb_port = 80

        return:
            slb_rsp_dict = {
                'all': 'rsp-2zexxxxxxxxxx', //默认的服务器组id，没有则为字符串None
                'www.xx.cn/rest': 'rsp-2zexxxxxxxxxxx' //域名+url和对应的服务器组id
            }
        """

        from aliyunsdkslb.request.v20140515.DescribeLoadBalancerHTTPListenerAttributeRequest import DescribeLoadBalancerHTTPListenerAttributeRequest
        request = DescribeLoadBalancerHTTPListenerAttributeRequest()
        request.set_accept_format('json')
        request.set_ListenerPort(slb_port)
        request.set_LoadBalancerId(slb_id)
        response = self.client.do_action_with_exception(request)

        #先获取默认虚拟服务器
        res_dict = json.loads(response)
        slb_rsp_dict = {}
        if "VServerGroupId" in res_dict.keys():
            slb_rsp_dict["all"] = res_dict["VServerGroupId"]
        else:
            slb_rsp_dict["all"] = "None"

        #不为空则加入到字典
        if len(res_dict["Rules"]["Rule"]) > 0:
            for i in res_dict["Rules"]["Rule"]:
                if "Url" in i.keys():
                    domain_url = i["Domain"] + i["Url"]
                    slb_rsp_dict[domain_url] = i["VServerGroupId"]
                else:
                    slb_rsp_dict[i["Domain"]] = i["VServerGroupId"]
        return slb_rsp_dict

    def get_slb_tcp(self, slb_id, slb_port):
        """查看SLB中TCP协议和端口所定义的虚拟服务器组，TCP没法配置转发，所以只有默认服务器组

        argvs:
            slb_id = "lb-xxxxxxxxxxxxx"
            slb_port = 80

        return:
            rsp_id = 'rsp-2zexxxxxxxxxx' //监听配置的虚拟服务器组，如果用的默认配置这里则为字符串"None"
        """

        from aliyunsdkslb.request.v20140515.DescribeLoadBalancerTCPListenerAttributeRequest import DescribeLoadBalancerTCPListenerAttributeRequest
        request = DescribeLoadBalancerTCPListenerAttributeRequest()
        request.set_accept_format('json')
        request.set_ListenerPort(slb_port)
        request.set_LoadBalancerId(slb_id)
        response = self.client.do_action_with_exception(request)

        res_dict = json.loads(response)
        slb_rsp_dict = {}
        if "VServerGroupId" in res_dict.keys():
            slb_rsp_dict["all"] = res_dict["VServerGroupId"]
        else:
            slb_rsp_dict["all"] = "None"
        return slb_rsp_dict

    def get_slb_rsp(self, slb_rsp_id):
        """获取服务器组中所对应的后端服务器ID和端口号
        
        argvs:
            slb_rsp_id = "rsp-2zexxxxxxxxx"

        return:
            slb_ecs_dict = {
                'i-2zexxxxxxxxx': 8080, 
                'i-2zexxxxxxxxx': 8080
            }
        """

        from aliyunsdkslb.request.v20140515.DescribeVServerGroupAttributeRequest import DescribeVServerGroupAttributeRequest

        request = DescribeVServerGroupAttributeRequest()
        request.set_accept_format('json')
        request.set_VServerGroupId(slb_rsp_id)
        response = self.client.do_action_with_exception(request)

        slb_ecs_dict = {}
        res_dict = json.loads(response)
        for i in res_dict["BackendServers"]["BackendServer"]:
            slb_ecs_dict[i["ServerId"]] = i["Port"]
        return slb_ecs_dict

    def get_ddos_domain(self):
        """查询防护了哪些域名

        return:
            ddos_domain_list = ['www.xx.cn', 'one.xx.cn']
        """

        request = CommonRequest()
        request.set_accept_format('json')
        request.set_domain('ddoscoo.cn-hangzhou.aliyuncs.com')
        request.set_method('POST')
        request.set_protocol_type('https')
        request.set_version('2020-01-01')
        request.set_action_name('DescribeDomains')
        request.add_query_param('RegionId', "cn-hangzhou")
        response = self.client.do_action(request)
        res_dict = json.loads(response)
        ddos_domain_list = res_dict["Domains"]
        return ddos_domain_list

    def get_ddos_info(self, ddos_domain):
        """根据域名获取具体的防护配置

        argvs:
            ddos_domain = "www.xx.cn"

        return:
            ddos_info_dict = {
                'bk_is_https': '0' //是否开启https
                'ddos_source_list': ['1.1.1.2'], //后端对应的地址列表
                'ddos_ssl_name': '3610901.pem', //使用的证书名称，如果只http则为字符串None
                'bk_http2': "0", //是否开启了http2
                'bk_https': "0", //是否强制https
                'bk_http_source': "0" //是否强制http回源
                'bk_inst_name' : "asdadad.ddos.com" //域名对应的cname地址
            }
        """

        request = CommonRequest()
        request.set_accept_format('json')
        request.set_domain('ddoscoo.cn-hangzhou.aliyuncs.com')
        request.set_method('POST')
        request.set_protocol_type('https')
        request.set_version('2020-01-01')
        request.set_action_name('DescribeWebRules')
        request.add_query_param('RegionId', "cn-hangzhou")
        request.add_query_param('PageSize', "10")
        request.add_query_param('Domain', ddos_domain)
        response = self.client.do_action(request)
        res_dict = json.loads(response)
        res_dict = res_dict["WebRules"][0]
        ddos_info_dict = {}

        #源地址列表
        ddos_source_list = []
        for i in res_dict["RealServers"]:
            ddos_source_list.append(i["RealServer"])

        #加到字典里
        ddos_info_dict["ddos_source_list"] = ddos_source_list
        ddos_info_dict["bk_inst_name"] = res_dict["Cname"]

        #获取证书名称
        try:
            ddos_info_dict["bk_ssl_name"] = res_dict["CertName"]
            ddos_info_dict["bk_is_https"] = "1"
        except:
            ddos_info_dict["bk_ssl_name"] = "None"
            ddos_info_dict["bk_is_https"] = "0"

        if ddos_info_dict["bk_is_https"] is False:
            ddos_info_dict["bk_http2"] = "0"
        else:
            ddos_info_dict["bk_http2"] = "1"

        if res_dict["Http2HttpsEnable"] is False:
            ddos_info_dict["bk_https"] = "0"
        else:
            ddos_info_dict["bk_https"] = "1"

        if res_dict["Https2HttpEnable"] is False:
            ddos_info_dict["bk_http_source"] = "0"
        else:
            ddos_info_dict["bk_http_source"] = "1"

        return ddos_info_dict

    def get_waf_domain(self):
        """查看当前waf防护的域名列表

        return:
            waf_domain_list = ['www.xx.cn', 'one.xx.cn']
        """

        from aliyunsdkwaf_openapi.request.v20190910.DescribeDomainNamesRequest import DescribeDomainNamesRequest

        request = DescribeDomainNamesRequest()
        request.set_accept_format('json')
        request.set_InstanceId(self.cfg['aliyun']['waf_id'])
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        return res_dict["DomainNames"]

    def get_waf_info(self, waf_domain):
        """查看

        argvs:
            waf_domain = "www.xx.cn"

        return:
            waf_info_dict = {
                src_ip_list = ["1.1.1.1"] //源地址列表
                bk_inst_name = "xx.waf.com" //名称
                bk_http_source = "0" //是否开启回源
                bk_https = "0" //是否强制https
                bk_waf_slb = "0" //负载均衡的算法
                bk_is_https = "0" //是否开启了https
            }

        """
        from aliyunsdkwaf_openapi.request.v20190910.DescribeDomainRequest import DescribeDomainRequest

        request = DescribeDomainRequest()
        request.set_accept_format('json')
        request.set_InstanceId(self.cfg['aliyun']['waf_id'])
        request.set_Domain(waf_domain)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        waf_info_dict = {}
        #定义的防护类型
        protect_type_list = ['waf','dld','tamperproof','antihijack','dlp','normalized','bot_crawler','bot_intelligence', \
        'antifraud','bot_algorithm','bot_wxbb','bot_wxbb_pkg','ac_cc','ac_blacklist','ac_highfreq',\
        'ac_dirscan','ac_scantools','ac_collaborative','ac_custom']

        waf_info_dict["src_ip_list"] = res_dict["Domain"]["SourceIps"]
        waf_info_dict["bk_inst_name"] = res_dict["Domain"]["Cname"].lower()
        waf_info_dict["bk_http_source"] = str(res_dict["Domain"]["HttpToUserIp"])
        waf_info_dict["bk_https"] = str(res_dict["Domain"]["HttpsRedirect"])
        waf_info_dict["bk_waf_slb"] = str(res_dict["Domain"]["LoadBalancing"])

        if res_dict["Domain"]["HttpsPort"]:
            waf_info_dict["bk_is_https"] = "1"
            waf_info_dict["bk_ssl_name"] = self.get_waf_ssl(waf_domain)
        else:
            waf_info_dict["bk_is_https"] = "0"
            waf_info_dict["bk_ssl_name"] = "None"

        #字段
        for protect_type in protect_type_list:
            start_status = self.get_waf_protect(waf_domain, protect_type)
            waf_info_dict[protect_type] = str(start_status)

        return waf_info_dict

    def get_waf_protect(self, waf_domain, protect_type):
        """查看

        argvs:
            waf_domain = "www.xx.cn"
            protect_type = "bot_intelligence" //防护类型

        return:
            start_status = 0 //1开启或0关闭
        """

        from aliyunsdkwaf_openapi.request.v20190910.DescribeProtectionModuleStatusRequest import DescribeProtectionModuleStatusRequest

        request = DescribeProtectionModuleStatusRequest()
        request.set_accept_format('json')
        request.set_Domain(waf_domain)
        request.set_DefenseType(protect_type)
        request.set_InstanceId(self.cfg['aliyun']['waf_id'])
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        return res_dict["ModuleStatus"]

    def get_waf_ssl(self, waf_domain):
        """获取waf的证书

        argvs:
            waf_domain: "www.xx.cn"

        return:
            ssl_name: "cert-232dd"
        """

        from aliyunsdkwaf_openapi.request.v20190910.DescribeCertificatesRequest import DescribeCertificatesRequest

        request = DescribeCertificatesRequest()
        request.set_accept_format('json')
        request.set_InstanceId(self.cfg['aliyun']['waf_id'])
        request.set_Domain(waf_domain)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        #证书名称
        return res_dict["Certificates"][0]["CertificateName"]

    def get_rds_id(self):
        """获取账号下实例id号

        return:
            rds_id_list = ["xxxx", "xxxx"]
        """

        from aliyunsdkrds.request.v20140815.DescribeDBInstancesRequest import DescribeDBInstancesRequest
        request = DescribeDBInstancesRequest()
        request.set_accept_format('json')
        request.set_PageSize(100)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        rds_id_list = []
        for rds_info in res_dict["Items"]["DBInstance"]:
            rds_id_list.append(rds_info["DBInstanceId"])

        return rds_id_list

    def get_rds_info(self, rds_id):
        """获取具体的实例信息

        argvs:
            rds_id = "xxxx"

        return:
            rds_info_dict = {
                "bk_rds_name": "UAT-会员",
                "bk_int_ip": "xxx.mysql.com",
                "bk_version": "mysql 5.7",
                "bk_mem": "4000",
                "bk_disk": "200",
                "bk_connect": "3000",
                "bk_cpu": "4",
                "bk_vpc": "uat-vpc",
            }
        """

        from aliyunsdkrds.request.v20140815.DescribeDBInstanceAttributeRequest import DescribeDBInstanceAttributeRequest
        request = DescribeDBInstanceAttributeRequest()
        request.set_accept_format('json')
        request.set_DBInstanceId(rds_id)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        rds_info_dict = {}
        rds_info = res_dict["Items"]["DBInstanceAttribute"][0]
        rds_info_dict["bk_rds_name"] = rds_info["DBInstanceDescription"]
        rds_info_dict["bk_int_ip"] = rds_info["ConnectionString"]
        rds_info_dict["bk_version"] = rds_info["Engine"] + " " + rds_info["EngineVersion"]
        rds_info_dict["bk_mem"] = str(rds_info["DBInstanceMemory"])
        rds_info_dict["bk_disk"] = str(rds_info["DBInstanceStorage"])
        rds_info_dict["bk_iops"] = str(rds_info["MaxIOPS"])
        rds_info_dict["bk_connect"] = str(rds_info["MaxConnections"])
        rds_info_dict["bk_cpu"] = str(rds_info["DBInstanceCPU"])
        rds_info_dict["bk_vpc"] = self.vpc_info_dict[rds_info["VpcId"]]

        return rds_info_dict

    def get_drds_id(self):
        """获取账号下PolarDB-X 1.0实例id号

        return:
            drds_id_list = ["xxxx", "xxxx"]
        """

        from aliyunsdkdrds.request.v20190123.DescribeDrdsInstancesRequest import DescribeDrdsInstancesRequest
        request = DescribeDrdsInstancesRequest()
        request.set_accept_format('json')
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        drds_id_list = []
        for drds_info in res_dict["Instances"]["Instance"]:
            drds_id_list.append(drds_info["DrdsInstanceId"])

        return drds_id_list

    def get_drds_info(self, drds_id):
        """获取drds的详细信息

        argvs:
            drds_id = "drds-xsxsds"

        return:
            drds_info_dict = {
                "bk_inst_name": "drds-xxxx",
                "bk_int_ip": "drds-xxx.drds.com",
                "bk_mysql_version": "5",
                "bk_spec": "4c8g",
                "bk_drds_name": "uat-drds",
                "bk_vpc": "uat环境vpc",
            }
        """

        from aliyunsdkdrds.request.v20190123.DescribeDrdsInstanceRequest import DescribeDrdsInstanceRequest
        request = DescribeDrdsInstanceRequest()
        request.set_accept_format('json')
        request.set_DrdsInstanceId(drds_id)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        drds_info_dict = {}
        drds_info_dict["bk_inst_name"] = drds_id
        drds_info_dict["bk_int_ip"] = drds_id + ".drds.aliyuncs.com"
        drds_info_dict["bk_mysql_version"] = str(res_dict["Data"]["MysqlVersion"])
        tmp_list = res_dict["Data"]["InstanceSpec"].split('.')
        drds_info_dict["bk_spec"] = tmp_list[3]
        drds_info_dict["bk_drds_name"] = res_dict["Data"]["Description"]
        for vpc_info in res_dict["Data"]["Vips"]["Vip"]:
            if "VswitchId" in vpc_info.keys():
                drds_info_dict["bk_vpc"] = self.vpc_info_dict[vpc_info["VpcId"]]

        return drds_info_dict

    def get_redis_id(self):
        """查询实例id

        return:
            redis_id_list = ["r-2exadax"]
        """

        from aliyunsdkr_kvstore.request.v20150101.DescribeInstancesRequest import DescribeInstancesRequest
        request = DescribeInstancesRequest()
        request.set_accept_format('json')
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        redis_id_list = []
        for redis_info in res_dict["Instances"]["KVStoreInstance"]:
            redis_id_list.append(redis_info["InstanceId"])

        return redis_id_list

    def get_redis_info(self, redis_id):
        """查询具体信息

        argvs:
            redis_id = ""

        return:
            redis_info_dict = {
    


            }
        """

        from aliyunsdkr_kvstore.request.v20150101.DescribeInstanceAttributeRequest import DescribeInstanceAttributeRequest
        request = DescribeInstanceAttributeRequest()
        request.set_accept_format('json')
        request.set_InstanceId(redis_id)
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        redis_info_dict = {}
        redis_info = res_dict["Instances"]["DBInstanceAttribute"][0]
        redis_info_dict["bk_inst_name"] = redis_id
        redis_info_dict["bk_bandwidth"] = str(redis_info["Bandwidth"])
        redis_info_dict["bk_mem"] = str(redis_info["Capacity"])
        redis_info_dict["bk_int_ip"] = redis_info["ConnectionDomain"]
        redis_info_dict["bk_connect"] = str(redis_info["Connections"])
        redis_info_dict["bk_version"] = redis_info["EngineVersion"]
        redis_info_dict["bk_redis_name"] = redis_info["InstanceName"]
        redis_info_dict["bk_qps"] = str(redis_info["QPS"])
        redis_info_dict["bk_vpc"] = self.vpc_info_dict[redis_info["VpcId"]]

        return redis_info_dict

    def get_edas_id(self):
        """edas的id号
        
        return:
            edas_id_list = [
                {
                    "edas_id": "3dsd-w2a-xada-da",
                    "edas_name": "uat_business_portal",
                    "edas_type": "War",
                },
            ] 
        """

        request = CommonRequest()
        request.set_accept_format('json')
        request.set_method('POST')
        request.set_protocol_type('https')
        request.set_domain('edas.cn-beijing.aliyuncs.com')
        request.set_version('2017-08-01')
        request.add_query_param('RegionId', "cn-beijing")
        request.add_header('Content-Type', 'application/json')
        request.set_uri_pattern('/pop/v5/app/app_list')
        body = '''{}'''
        request.set_content(body.encode('utf-8'))
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        edas_id_list = []
        for edas_info in res_dict["ApplicationList"]["Application"]:
            tmp_dict = {}
            tmp_dict["edas_id"] = edas_info["AppId"]
            tmp_dict["edas_name"] = edas_info["Name"]
            tmp_dict["edas_type"] = edas_info["ApplicationType"]
            edas_id_list.append(tmp_dict)

        return edas_id_list

    def get_edas_ecu(self, edas_id):
        """获取对应edas中部署的ECSip
        
        argvs:
            edas_id = "3dsd-w2a-xada-da"

        return:
            ecu_ip_list = ["1.1.1.1"]
            }
        """

        request = CommonRequest()
        request.set_accept_format('json')
        request.set_method('POST')
        request.set_protocol_type('https') # https | http
        request.set_domain('edas.cn-beijing.aliyuncs.com')
        request.set_version('2017-08-01')
        request.add_query_param('RegionId', "cn-beijing")
        request.add_query_param('AppId', edas_id)
        request.add_header('Content-Type', 'application/json')
        request.set_uri_pattern('/pop/v5/resource/ecu_list')
        body = '''{}'''
        request.set_content(body.encode('utf-8'))
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        ecu_ip_list = []
        for ecu_info in res_dict["EcuInfoList"]["EcuEntity"]:
            ecu_ip_list.append(ecu_info["IpAddr"])

        return ecu_ip_list

    def get_edas_tomcat(self, edas_id):
        """获取对应tomcat信息
        
        argvs:
            edas_id = "3dsd-w2a-xada-da"

        return:
            tomcat_info_dict = {
                "bk_port" = "8080",
                "bk_encoding" = "ISO-8859-1",
                "bk_threads" = "400"
            }
        """

        request = CommonRequest()
        request.set_accept_format('json')
        request.set_method('GET')
        request.set_protocol_type('https')
        request.set_domain('edas.cn-beijing.aliyuncs.com')
        request.set_version('2017-08-01')
        request.add_query_param('RegionId', "cn-beijing")
        request.add_query_param('AppId', edas_id)
        request.add_header('Content-Type', 'application/json')
        request.set_uri_pattern('/pop/v5/app/container_config')
        body = '''{}'''
        request.set_content(body.encode('utf-8'))
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        tomcat_info_dict = {}
        tomcat_info = res_dict["ContainerConfiguration"]
        tomcat_info_dict["bk_port"] = str(tomcat_info["HttpPort"])
        tomcat_info_dict["bk_encoding"] = tomcat_info["URIEncoding"]
        tomcat_info_dict["bk_threads"] = str(tomcat_info["MaxThreads"])

        return tomcat_info_dict


    def get_edas_jvm(self, edas_id):
        """获取对应jvm信息
        
        argvs:
            edas_id = "3dsd-w2a-xada-da"

        return:
            jvm_info_dict = {
                "bk_maxheap": "80000",
                "bk_permsize": "8000",
                "bk_minheap": "400",
                "bk_options": "-Dhsf.server.min.poolsize=200"
            }
        """

        request = CommonRequest()
        request.set_accept_format('json')
        request.set_method('GET')
        request.set_protocol_type('https')
        request.set_domain('edas.cn-beijing.aliyuncs.com')
        request.set_version('2017-08-01')
        request.add_query_param('RegionId', "cn-beijing")
        request.add_query_param('AppId', edas_id)
        request.add_header('Content-Type', 'application/json')
        request.set_uri_pattern('/pop/v5/app/app_jvm_config')
        body = '''{}'''
        request.set_content(body.encode('utf-8'))
        response = self.client.do_action_with_exception(request)
        res_dict = json.loads(response)

        jvm_info_dict = {}
        jvm_relation_dict = {
            "MaxHeapSize": "bk_maxheap", 
            "MaxPermSize": "bk_permsize",
            "MinHeapSize": "bk_minheap",
            "Options": "bk_options"
        }
        if "JvmConfiguration" in res_dict.keys():
            jvm_info = res_dict["JvmConfiguration"]
            for k, v in jvm_info.items():
                jvm_info_dict[jvm_relation_dict[k]] = str(v)

            #补齐
            for v in jvm_relation_dict.values():
                if v not in jvm_info_dict.keys():
                    jvm_info_dict[v] = str(0)

        else:
            for v in jvm_relation_dict.values():
                jvm_info_dict[v] = str(0)

        return jvm_info_dict
