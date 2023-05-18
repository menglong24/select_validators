import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
#输出dataframe时数据可以对齐
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)
# 画图显示中文
plt.rcParams['font.sans-serif'] = ['SimHei']



class SelectValidators():
    def __init__(self, _network):
        self.network = _network
        self.my_subscan_api_key = ''  # 我的 subscan api 密钥
        self.max_row = 100  # subscan api 一页最多有多少行（row）
        self.rows = []      # 验证人总信息表
        self.df_validators = pd.DataFrame()
        self.filepath_validators_list = 'C://Users//张建国//Desktop//波卡视频//66 波卡验证人自动筛选//新方法//' + self.network +'_validators.xlsx'

        if self.network == 'polkadot':
            self.average_stake = 1.857 * 10**6   # 当前的全网平均质押量
            self.validator_counts = 297          # 当前时代的验证人总数
            self.coefficient = 1.2               # 验证人的质押量不能超过平均质押量的多少
            self.fee_upper_limit = 0.1           # 验证人手续费最高是多少
            self.page_counts = 3                 # 一页最多100条数据，总共需要多少数据（波卡是3页，ksm是10页）
            self.days = 50                       # 验证人在过去50天连续出块，如果去除当前时代，是49天
        elif self.network == 'kusama':
            self.average_stake = 7113.3    # 当前的全网平均质押量
            self.validator_counts = 1000   # 当前时代的验证人总数
            self.coefficient = 1.2         # 验证人的质押量不能超过平均质押量的多少
            self.fee_upper_limit = 0.1     # 验证人手续费最高是多少
            self.page_counts = 10          # 一页最多包含100条验证人数据，总共需要多少数据
            self.days = 30                 # 验证人在过去30天连续出块，如果去除当前时代，是29天
        else:
            print('输入的网络名称为{0}。网络输入错误！请输入polkadot/kusama'.format(self.network))
            time.sleep(30)


    # 利用subscan api获取一页的验证人数据（地址，手续费，总质押量）
    def get_one_page(self, _page):
        url = 'https://' + self.network + '.api.subscan.io/api/scan/staking/validators'
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.my_subscan_api_key
        }
        data = {
            "row": self.max_row, 
            "page": _page
            } 
        response = requests.post(url, headers=headers, json=data)
        response_dict = response.json()
        print("第{0}页数据获取完毕，状态码为{1}".format(_page+1, response.status_code))
        # 在收到的数据中获取几个关键字段（地址，手续费，总质押量）
        for item in response_dict['data']['list']:
            row = {
                'stash_account_display': item['stash_account_display']['address'],
                'validator_prefs_value': item['validator_prefs_value'],
                'bonded_total': item['bonded_total']
            }
            self.rows.append(row)


    # 获取所有验证人数据（地址，手续费，总质押量），并整理为dataframe格式
    def get_validators_list(self):
        for i in range(self.page_counts):
            print("正在获取第{0}页数据，共{1}页".format(i+1, self.page_counts))
            self.get_one_page(i)
        self.df_validators = pd.DataFrame(self.rows, columns=['stash_account_display', 'validator_prefs_value', 'bonded_total']) # 使用pandas创建数据框
        self.df_validators.rename(columns={'validator_prefs_value':'fee'}, inplace=True)    # 将手续费重命名
        self.df_validators['fee'] = self.df_validators['fee'] / 1e9                              # 处理手续费
        self.df_validators['bonded_total'] = self.df_validators['bonded_total'].apply(float)
        if self.network == 'polkadot':
            self.df_validators['bonded_total'] = self.df_validators['bonded_total'] / 1e10           # 处理总质押量
        elif self.network == 'kusama':
            self.df_validators['bonded_total'] = self.df_validators['bonded_total'] / 1e12           # 处理总质押量
        self.df_validators.sort_values('fee', axis = 0, ascending = True, inplace = True)   # 按照手续费对验证人进行升序排名
        self.df_validators = self.df_validators[(self.df_validators['fee']<=self.fee_upper_limit) & (self.df_validators['bonded_total']<=self.coefficient*self.average_stake)].copy()
        print('手续费小于等于{0}且总质押量不超过平均质押量{1}  {2}倍的验证人有{3}个'.format(self.fee_upper_limit, self.average_stake, self.coefficient, self.df_validators.shape[0]))
        return self.df_validators


    # 明确单个验证人是否在过去50天连续出块，并整理到 df 中
    def produce_block_continuously_one(self, _address):
        url = 'https://' + self.network + '.api.subscan.io/api/scan/staking/era_stat'
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.my_subscan_api_key
        }
        data = {"row": self.days, 
                "page": 0, 
                "address":_address
            }
        response = requests.post(url, headers=headers, json=data)
        response_dict = response.json()
        return response_dict


    # 明确所有验证人是否在过去50天连续出块，并整理到 df 中
    def produce_block_continuously_all(self, _df_validators):
        continue_number = int(_df_validators.loc[0, 'continue_number'])
        for i in range(continue_number, _df_validators.shape[0]):
            address = _df_validators.loc[i, 'stash_account_display']  # 获取验证人的地址
            era_dict = self.produce_block_continuously_one(address)  # 获取验证人在过去一段时间内的出块情况（哪些时代被选举上了？时代得分是多少？）
            df_era = pd.DataFrame(era_dict['data']['list'])  # 将数据由字典格式转换为 df 格式
            current_era = df_era['era'].iloc[0]  # 获取当前时代（每个验证人都是活跃验证人，当前时代均相同）
            long_ago_era = df_era['era'].iloc[-1] # 获取 days 天前的时代
            # 如果此条件成立，表示验证人连续出块（用 1 表示）。否则（两个时代差值过大）表示验证人在过去 days 天没有连续出块（用 0 表示）
            if (current_era - long_ago_era) == (self.days - 1):
                _df_validators.loc[i, 'produce_block_continuously'] = 1  
            else:
                _df_validators.loc[i, 'produce_block_continuously'] = 0
            _df_validators.loc[i, 'mean'] = df_era['reward_point'][1:].mean() # 计算验证人在其最近的出块的 days 个时代中的均值（如果不连续出块，没有参考意义）
            _df_validators.loc[i, 'std'] = df_era['reward_point'][1:].std()  # 计算验证人在其最近的出块的 days 个时代中的标准差（如果不连续出块，没有参考意义）
            print("第{0}个验证人的地址是{1}，是否在过去连续出块{2}".format(i, address, (current_era - long_ago_era) == (self.days - 1)))
            _df_validators.loc[0, 'continue_number'] = i + 1 # 第 i 个验证人的数据获取完毕，如果程序中断的话，之后从 i + 1 开始
            # if i == 2:
            #     print(1/0)
        return _df_validators





    # 对低手续费验证人的原始平均时代得分进行调整，并画图
    def modify_low_fee_validators(self, _df_validators):
        _df_validators['mean_modify'] = ''  # 创建新的列，调整后的验证人平均时代得分
        _df_validators['mean_modify'] = _df_validators['mean']*(1-_df_validators['fee'])/((_df_validators['bonded_total']-_df_validators['over_subscribed'])/self.average_stake)
        _df_validators = _df_validators.sort_values(by=['mean_modify'],ascending=[False])
        print(_df_validators)
        _df_validators.to_excel(self.filepath_validators_list, index=None)

        plt.figure(1)
        _df_validators['mean_modify'].plot.bar()
        plt.xlabel('验证人序号')
        plt.ylabel('时代得分均值（修正）')
        plt.savefig('时代得分均值（修正）.pdf')

        plt.figure(2)
        _df_validators['std'].plot.bar()
        plt.xlabel('验证人序号')
        plt.ylabel('标准差')
        plt.savefig('标准差.pdf')

        plt.show()





# 步骤：
network = 'kusama'  # 设置验证人网络（polkadot/kusama）
# 1：修改最前面的文件地址及参数


# # 2：运行以下程序，获取所有低手续费验证人的原始数据（总质押量，手续费） 并保存为excel格式
# Validators = SelectValidators(network) # 创建验证人实例
# df_validators = Validators.get_validators_list() # 获取低手续费，低质押量的验证人列表
# df_validators['continue_number'] = 0  # 指示第3步从第几个验证人开始获取时代得分（以防程序中断从头开始）
# df_validators['produce_block_continuously'] = ''  # 创建新的列，是否连续出块标识符
# df_validators['mean'] = ''                 # 创建新的列，验证人在过去出块的 days 天的平均时代得分
# df_validators['std'] = ''                  # 创建新的列，验证人在过去出块的 days 天的时代得分标准差
# df_validators.to_excel(Validators.filepath_validators_list, index=None)
# ### 中断程序

# # 3：打开表格，手动添加一列（over_subscribed）表示验证人的超额认购数量


# # # 4：运行以下程序，获取所有低手续费验证人的原始数据（总质押量，手续费,平均时代得分）如果程序中断，则自动保存序号，再次执行，从序号处重新开始获取数据
# #                  对低手续费验证人的原始平均时代得分进行调整，并画图
# Validators = SelectValidators(network) # 创建验证人实例
# df_validators = pd.read_excel(Validators.filepath_validators_list)
# try:
#     print("获取的验证人总数为{0}".format(df_validators.shape[0]))  # 获取验证人总数
#     df_validators = Validators.produce_block_continuously_all(df_validators)
# finally:
#     df_validators.to_excel(Validators.filepath_validators_list, index=None)

# Validators.modify_low_fee_validators(df_validators)  # 获取了全部验证人的时代得分后，对其进行修正和画图


