from dateutil import parser
import pymongo, datetime, bson, configparser
import logging, json, requests, threading
import sys


class BkCmdb():
    """蓝鲸CMDB的API操作和数据库操作

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

        #[API相关内容]
        self.bk_url = self.cfg['bk']['bk_url']
        self.post_header = {'Content-Type': 'application/json'}
        bk_app_code = self.cfg['bk']['bk_app_code']
        bk_app_secret = self.cfg['bk']['bk_app_secret']
        bk_username = self.cfg['bk']['bk_username']
        self.post_data = {
            "bk_app_code": bk_app_code,
            "bk_app_secret": bk_app_secret,
            "bk_username": bk_username,
        }

        #[mongodb数据库相关内容]
        data_ip = self.cfg['bk']['data_ip']
        data_port = self.cfg['bk']['data_port']
        data_user = self.cfg['bk']['data_user']
        data_pass = self.cfg['bk']['data_pass']
        client = pymongo.MongoClient(host=data_ip, port=int(data_port))
        db = client.admin
        db.authenticate(data_user, data_pass, mechanism='SCRAM-SHA-1')
        self.db = client['cmdb']

        #[用于记录要添加的实例信息和实例关联信息的变量，后续用于和cmdb中比对后清理]
        self.public_inst_dict = {}
        self.public_asst_dict = {}
        self.tmp_list = {}

    def get_host_id(self, inq_dict):
        """根据字典来查询主机id，不存在主机则返回0
    
        argvs:
            inq_dict = {"bk_host_innerip":"1.1.1.1"}

        return:
            host_id = 30
        """

        mycol = self.db['cc_HostBase']
        mydoc = mycol.find(inq_dict)

        try:
            host_id = mydoc[0]['bk_host_id']
        except:
            host_id = 0
        return host_id

    def create_host(self, host_ip):
        """创建主机

        argvs:
            host_ip = "1.1.1.1"
        """

        req_data = self.post_data
        req_data["bk_biz_id"] = 3
        req_data["host_info"] = {
            "0": {
                "bk_host_innerip": host_ip,
                "bk_cloud_id": 0,
                "import_from": "3"
            }
        }

        url = self.bk_url + "/api/c/compapi/v2/cc/add_host_to_resource/"
        req = requests.post(url, data=json.dumps(req_data), headers=self.post_header)
        bk_req = req.json()

        logging.info("创建主机:" + host_ip)
        logging.debug(bk_req)

    def get_host(self, inq_dict):
        """根据查询字段来查询主机信息

        argvs:
            inq_dict = {"bk_host_type":"0"}

        return:
            host_info_list = ["bk_host_type":"0"]
        """

        mycol = self.db['cc_HostBase']
        mydoc = mycol.find(inq_dict)

        mydoc = mycol.find(inq_dict)

        host_info_list = []
        for i in mydoc:
            host_info_list.append(i)
        return host_info_list

    def update_host(self, host_id, inq_dict):
        """更新主机

        argvs:
            host_id = 3
            inq_dict = {"bk_host_type":"0"}
        """

        mycol = self.db['cc_HostBase']
        myquery = {"bk_host_id": host_id}
        newvalues = {"$set": inq_dict}
        mycol.update_one(myquery, newvalues)
 
        logging.info("更新主机:" + str(host_id))
        logging.debug(inq_dict)

    def get_host_mod(self, host_id):
        """根据主机id查询绑定了哪些模块的id号
    
        argvs:
            host_id = 10

        return:
            mod_id_list = [23,45]
        """

        mod_id_list = []
        mycol = self.db['cc_ModuleHostConfig']
        myquery = { "bk_host_id": host_id }
        mydoc = mycol.find(myquery)

        for x in mydoc:
            mod_id_list.append(x['bk_module_id'])
        return mod_id_list

    def get_mod(self, inq_dict):
        """根据查询字典来获取模块信息
    
        argvs:
            inq_dict = {"bk_module_id": "32"}

        return:
            mod_info_list = [
                {
                    "bk_set_id": 4, //集群id
                    "bk_module_name": "gse_btsvr", //模块名称
                    "bk_biz_id": 2, //业务id
                    "bk_module_id": 19, //模块id
                    "bk_parent_id": 4 //父节点id，模块上一级是集群，和bk_set_id等值
                },
            ]
        """

        mycol = self.db['cc_ModuleBase']
        mydoc = mycol.find(inq_dict)

        mod_info_list = []
        for i in mydoc:
            mod_info_list.append(i)
        return mod_info_list

    def get_mod_proc(self, mod_name):
        """根据模块名称获取所绑定这个模块的进程id号
    
        argvs:
            mod_name = "database"

        return:
            proc_id_list = [32, 45]
        """

        mycol = self.db['cc_Proc2Module']
        myquery = { "bk_module_name": mod_name }
        mydoc = mycol.find(myquery)

        proc_id_list = []
        for i in mydoc:
            proc_id_list.append(i["bk_process_id"])
        return proc_id_list

    def update_mod(self, mod_id, inq_dict):
        """更新模块的信息
    
        argvs:
            mod_id = 30
            inq_dict = {"bk_module_name": "database"}
        """

        mycol = self.db['cc_ModuleBase']
        myquery = { "bk_module_id": mod_id }
        newvalues = { "$set": inq_dict }
        mycol.update_one(myquery, newvalues)

    def create_inst(self, inq_dict):
        """根据字典来创建实例，字典中为模型字段
    
        argvs:
            inq_dict = {"bk_inst_name":"生产-会员-内网"}
        """

        req_data = self.post_data
        req_data["bk_supplier_account"] = 0
        req_data = dict(req_data, **inq_dict)

        url = self.bk_url + "/api/c/compapi/v2/cc/create_inst/"
        req = requests.post(url, data=json.dumps(req_data), headers=self.post_header)
        bk_req = req.json()
        logging.info("创建实例:" + inq_dict["bk_inst_name"])
        logging.debug(inq_dict)
        logging.debug(bk_req)

    def update_inst(self, inq_dict):
        """根据传入的信息，对实例进行更新

        argvs:
            inq_dict = {"bk_inst_name":"生产-会员-内网", "bk_id" = "lb-xxxxxxxxxxx"}
        """

        logging.info("更新实例:" + inq_dict["bk_inst_name"])
        logging.debug(inq_dict)

        #通过名称匹配去更新其它数据
        mycol = self.db['cc_ObjectBase']
        myquery = { "bk_inst_name": inq_dict["bk_inst_name"] }
        del inq_dict["bk_inst_name"]
        newvalues = { "$set": inq_dict }
        mycol.update_one(myquery, newvalues)

    def add_inst(self, inq_dict):
        """添加inst信息

        argvs:
            inq_dict = {"bk_inst_name":"生产-会员-内网"}
        """

        #先查询全额数据，看是否有完全一致的
        if not self.get_inst(inq_dict):
            tmp_inq_dict = {}
            tmp_inq_dict["bk_inst_name"] = inq_dict["bk_inst_name"]
            
            #再只查询是否有这个名称的实例
            if self.get_inst(tmp_inq_dict):
                self.update_inst(inq_dict)
            else:
                self.create_inst(inq_dict)

        bk_obj_id = inq_dict["bk_obj_id"]
        self.public_inst_dict[bk_obj_id].append(inq_dict)

    def get_inst(self, inq_dict):
        """根据输入的字段查询实例信息

        argvs:
            inq_dict = {"bk_inst_name":"生产-会员-内网"}

        return:
            inst_info_list = [{"bk_inst_name":"生产-会员-内网"}]
        """
        mycol = self.db['cc_ObjectBase']
        mydoc = mycol.find(inq_dict)

        inst_info_list = []
        for i in mydoc:
            inst_info_list.append(i)
        return inst_info_list

    def del_inst(self, bk_obj_id, inst_id, bk_inst_name):
        """删除实例
        
        argvs:
            bk_obj_id = bk_slb //模型id
            inst_id = 28 //实例的id号
            bk_inst_name = "生产-会员-内网" //实例名称，用于显示
        """
        req_data = self.post_data
        req_data["bk_supplier_account"] = 0
        req_data["bk_obj_id"] = bk_obj_id
        req_data["delete"] = {"inst_ids":[inst_id]}

        url = self.bk_url + "/api/c/compapi/v2/cc/batch_delete_inst/"
        req = requests.post(url, data=json.dumps(req_data), headers=self.post_header)
        bk_req = req.json()

        logging.info("删除实例:" + bk_inst_name )
        logging.debug(bk_req)

    def get_asst(self, inq_dict):
        """根据查询字典，找到对应实例之间的关联信息

        argvs:
            inq_dict = {"bk_obj_id":"bk_slb"}

        return:
            asst_info_list = [{"bk_obj_id":"bk_slb"}]
        """

        mycol = self.db['cc_InstAsst']
        mydoc = mycol.find(inq_dict)

        #写到数组里
        asst_info_list = []
        for i in mydoc:
            asst_info_list.append(i)
        return asst_info_list

    def get_job_asst(self, inq_dict):
        """查询模型间的关联信息

        argvs:
            inq_dict = {"bk_obj_id":"bk_slb"}

        return:
            job_asst_list = [{"bk_obj_id":"bk_slb"}]
        """

        mycol = self.db['cc_ObjAsst']
        mydoc = mycol.find(inq_dict)

        #写到数组里
        job_asst_list = []
        for i in mydoc:
            job_asst_list.append(i)
        return job_asst_list

    def get_asst_lastid(self):
        """获取实例中最后可用的id号

        return:
            asst_id = 129
        """

        mycol = self.db['cc_InstAsst']
        mydoc = mycol.find().sort('_id', -1).limit(1)
        try:
            asst_id = mydoc[0]["id"]        
        except:
            asst_id = 0
        asst_id = asst_id + 1
        return asst_id

    def get_host(self, inq_dict):
        """查询主机信息

        argvs:
            inq_dict = {"bk_host_innerip":"192.168.1.2"}

        return:
            host_info_list = [{"bk_host_innerip":"192.168.1.2"}]
        """

        mycol = self.db['cc_HostBase']
        mydoc = mycol.find(inq_dict)

        #写到数组里
        host_info_list = []
        for i in mydoc:
            host_info_list.append(i)
        return host_info_list

    def create_asst(self, asst_id, inq_dict):
        """添加实例之家的关联信息

        argvs:
            asst_id: 138
            inq_dict: {"bk_obj_id":"bk_slb"}
        """

        nowtime = datetime.datetime.now()
        create_time = nowtime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        create_time = parser.parse(create_time)
        last_time = "0001-01-01T00:00:00Z"
        last_time = parser.parse(last_time)

        mycol = self.db['cc_InstAsst']
        mydict = {
            "bk_supplier_account" : "0", 
            "create_time" : create_time, 
            "last_time" : last_time
        }
        mydict.update(inq_dict)
        mydict["id"] = bson.int64.Int64(asst_id)
        mydict["bk_inst_id"] = bson.int64.Int64(inq_dict["bk_inst_id"])
        mydict["bk_asst_inst_id"] = bson.int64.Int64(inq_dict["bk_asst_inst_id"])

        mydoc = mycol.insert_one(mydict)
        logging.info("添加实例id" + str(inq_dict["bk_obj_id"]) + "到实例id" + str(inq_dict["bk_obj_asst_id"]) + "的关联信息")
        logging.debug(mydict)
        logging.debug(mydoc)

    def add_asst(self, bk_obj_id, bk_inst_name, bk_dest_keyword):
        """添加实例关联关系

        argvs:
            bk_obj_id = "bk_slb"
            bk_inst_name = "生产-会员-内网"
            bk_dest_keyword = "172.16.1.2" //目标实例的关键字
        """

        #查询实例信息
        inst_info_list = []

        #模型对应的模型关联信息
        inq_dict = {"bk_obj_id": bk_obj_id}
        job_asst_list = self.get_job_asst(inq_dict)

        #循环根据模型关系去找，例如和host、bk_tools模型绑定，那就循环查2次
        for asst_info_dict in job_asst_list:
            #先检测是否有东西，要退出2层break
            if inst_info_list:
                break

            #查找配置文件，没有则是空的
            try:
                match_field = self.cfg['bk_mod_field'][asst_info_dict["bk_asst_obj_id"]]
                match_field_list = match_field.split(',')
            except:
                match_field_list = []
            match_field_list.append("bk_inst_name")

            if match_field_list:
                #循环根据字段与值，去找这个实例是谁，放入列表中
                for inq_field in match_field_list:
                    if asst_info_dict["bk_asst_obj_id"] == "host":
                        inq_dict = {inq_field:bk_dest_keyword}
                        inst_info_list = self.get_host(inq_dict)
                    else:
                        #对于其它实例就要指定下这个实例的模型是啥
                        inq_dict = {inq_field:bk_dest_keyword, "bk_obj_id":asst_info_dict["bk_asst_obj_id"]}
                        inst_info_list =  self.get_inst(inq_dict)
                    #里面只可能有一个字段是匹配到值了，所以有了值就 并退出循环
                    if inst_info_list:
                        inst_info_list.append(asst_info_dict["bk_asst_obj_id"])
                        inst_info_list.append(asst_info_dict["bk_obj_asst_id"])
                        inst_info_list.append(asst_info_dict["bk_asst_id"])
                        break

        #查看是否有值，有则查看实例关联关系是否已经存在
        if inst_info_list:
            #这里取出源实例的id号
            if bk_obj_id == "host":
                inq_dict = {"bk_host_innerip": bk_inst_name}
                src_inst_info = self.get_host(inq_dict)
            else:
                inq_dict = {"bk_inst_name" : bk_inst_name}
                src_inst_info = self.get_inst(inq_dict)
            src_inst_id = src_inst_info[0]["bk_inst_id"]

            #找到目标实例的id号
            if inst_info_list[1] == "host":
                dest_inst_id = inst_info_list[0]["bk_host_id"]
                bk_asst_obj_id = "host"
            else:
                dest_inst_id = inst_info_list[0]["bk_inst_id"]
                bk_asst_obj_id = inst_info_list[0]["bk_obj_id"]

            #拿出关联信息，原实例对应的，然后重组筛选放到
            inq_dict = {
                "bk_inst_id":src_inst_id, 
                "bk_obj_id":bk_obj_id, 
                "bk_asst_inst_id":dest_inst_id,
                "bk_asst_obj_id":bk_asst_obj_id,
                "bk_obj_asst_id":inst_info_list[2],
                "bk_asst_id":inst_info_list[3]
            }
            inst_asst_dict = self.get_asst(inq_dict)
            if not inst_asst_dict:
                #获取唯一的id号
                asst_id = self.get_asst_lastid()
                self.create_asst(asst_id, inq_dict)

            #加到公共列表
            self.public_asst_dict[bk_obj_id].append(inq_dict)
        else:
            logging.warn(bk_inst_name + "实例没有找到与之关联的其它实例，请手工创建" + bk_dest_keyword)

    def del_asst(self, bk_obj_id, ast_id, asst_info_dict):
        """删除实例关联关系

        argvs:
            bk_obj_id = "bk_slb"
            ast_id = 25
            asst_info_dict = {"bk_obj_id":"bk_slb"} //用于显示
        """

        mycol = self.db['cc_InstAsst']
        myquery = { "id": ast_id }
        mycol.delete_one(myquery)
        
        #显示
        logging.info("删除实例" + asst_info_dict["bk_obj_id"] + "到" + asst_info_dict["bk_asst_obj_id"] + "关联关系")

    def clear_asst(self, bk_obj_id, real_asst_list):
        """清理cmdb中和源数据不符合的实例关联关系
        
        argvs:
            bk_obj_id = "bk_slb"
            real_asst_list = [{"bk_obj_id":"bk_slb"}] //这个模型真实的关联关系列表
        """

        logging.info("开始清理" + bk_obj_id + "模型中和源数据不符合的实例关联关系")

        #当前模块所有实例关联关系列表
        inq_dict = {"bk_obj_id" : bk_obj_id}
        all_asst_list = self.get_asst(inq_dict)

        if real_asst_list:
            #循环把需要的值加到私有的实例字典里
            filter_real_asst_list = []
            for asst_info_dict in all_asst_list:
                tmp_dict = {}
                for field_type in real_asst_list[0].keys():
                    tmp_dict[field_type] = asst_info_dict[field_type]
                filter_real_asst_list.append(tmp_dict)

            #从所有中循环，如果不在线上列表里就删除
            for tmp_dict in filter_real_asst_list:
                if tmp_dict not in real_asst_list:
                    asst_info_list = self.get_asst(tmp_dict)
                    self.del_asst(bk_obj_id, asst_info_list[0]["id"], tmp_dict)
        else:
            logging.warn("源数据没有查询到任何值，将cmdb中数值都清理掉")
            for tmp_dict in all_asst_list:
                asst_info_list = self.get_asst(tmp_dict)
                self.del_asst(bk_obj_id, asst_info_list[0]["id"], tmp_dict)

    def clear_inst(self, bk_obj_id, real_inst_list):
        """清理cmdb中和源数据不符合的实例

        argvs:
            bk_obj_id = "bk_slb"
            real_asst_list = [{"bk_obj_id":"bk_slb"}] //这个模型真实的关联关系列表
        """

        logging.info("开始清理" + bk_obj_id + "模型中和源数据不符合的实例")

        #当前模块下所有的实例信息列表
        inq_dict = {"bk_obj_id" : bk_obj_id}
        all_inst_list = self.get_inst(inq_dict)

        #查看公共里是否有，没有说明源数据里啥也没有，那CMDB里都要删除
        if real_inst_list:
            #循环把需要的值加到私有的实例字典里
            filter_real_inst_list = []
            for inst_info_dict in all_inst_list:
                tmp_dict = {}
                for field_type in real_inst_list[0].keys():
                    tmp_dict[field_type] = inst_info_dict[field_type]
                filter_real_inst_list.append(tmp_dict)
            #找出不同元素
            for tmp_dict in filter_real_inst_list:
                if tmp_dict not in real_inst_list:
                    inst_info_list = self.get_inst(tmp_dict)
                    #有时候bk_inst_name会莫名消失
                    if "bk_inst_name" in tmp_dict.keys():
                        self.del_inst(bk_obj_id, inst_info_list[0]["bk_inst_id"], tmp_dict["bk_inst_name"])
        else:
            logging.info("源数据没有查询到任何值，将cmdb中数值都清理掉")
            for tmp_dict in all_inst_list:
                inst_info_list = self.get_inst(tmp_dict)
                self.del_inst(bk_obj_id, inst_info_lost[0]["bk_inst_id"], tmp_dict["bk_inst_name"])

    def get_job_id(self):
        """查询模型的id号

        return:
            default_id_list = ["bk_server", "bk_slb"]
        """

        #系统自带的id排除掉
        job_id_list = []
        mycol = self.db['cc_ObjDes']
        myquery = { "bk_classification_id": "bk_network" }
        mydoc = mycol.find(myquery)
        for x in mydoc:
            job_id_list.append(x["bk_obj_id"])

        return default_id_list
