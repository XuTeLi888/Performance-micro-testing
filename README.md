# Micro-monitoring of performance
安卓性能测试软件
# 手机性能监控工具

这是一个基于WebUI的手机性能监控软件，可以通过有线ADB或无线ADB获取手机的各项性能指标。软件内置ADB环境，无需单独安装ADB工具即可使用。

## 功能特点

- 支持有线ADB和无线ADB连接
- 内置ADB环境，便携使用
- 获取设备基本信息：
  - 手机型号
  - 系统版本
  - 安卓API级别
- 实时监控以下性能指标：
  - FPS (帧率)
  - CPU频率 
  - GPU频率
  - CPU负载 (平均值)
  - GPU负载 (暂未实现)
  - 运行电流 (暂未实现)
  - 功率 (暂未实现)
- 数据可视化图表展示
- 数据导出功能

## 系统要求

- Python 3.6+
- 浏览器：Chrome, Firefox, Edge等现代浏览器
- ADB工具
- 安卓设备（已开启开发者选项和USB调试）
- 运行环境：Windows
- 注：精度较低，数据仅供参考

## 环境配置

1. 创建并激活Python虚拟环境（推荐）：
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   

2. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```

## 使用方法

1. 启动服务器：
   ```bash
   python server.py
   ```

2. 在浏览器中访问：`http://localhost:5000`

3. 连接设备：
   - 有线连接：通过USB连接手机，并确保已开启USB调试
   - 无线连接：输入手机IP地址进行连接

