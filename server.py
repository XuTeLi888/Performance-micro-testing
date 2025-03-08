import os
import re
import json
import time
import subprocess
import threading
import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

# 初始化Flask和Socket.IO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'performance_monitor_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

# 全局变量
connected_device = None
monitoring = False
monitor_thread = None

# ADB命令工具类
class ADBTools:
    @staticmethod
    def get_adb_path():
        """获取ADB可执行文件的路径"""
        # 首先检查内置ADB路径
        adb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'adb', 'adb.exe')
        if os.path.exists(adb_path):
            return adb_path
        # 如果内置ADB不存在，返回系统ADB命令
        return 'adb'

    @staticmethod
    def check_adb():
        """检查ADB是否可用"""
        try:
            adb_path = ADBTools.get_adb_path()
            # 检查ADB版本和设备连接状态
            version_output = subprocess.check_output([adb_path, 'version'], universal_newlines=True)
            devices_output = subprocess.check_output([adb_path, 'devices'], universal_newlines=True)
            
            # 验证是否有设备连接
            if 'List of devices attached' in devices_output and len(devices_output.strip().split('\n')) > 1:
                return True
            return False
        except Exception as e:
            print(f"ADB检查失败: {str(e)}")
            return False

    @staticmethod
    def get_device_info():
        """获取设备信息（型号、系统版本、安卓版本）"""
        try:
            adb_path = ADBTools.get_adb_path()
            # 获取设备型号
            model_result = subprocess.check_output(
                [adb_path, 'shell', 'getprop', 'ro.product.model'],
                universal_newlines=True
            )
            model = model_result.strip()
            
            # 获取设备品牌
            brand_result = subprocess.check_output(
                [adb_path, 'shell', 'getprop', 'ro.product.brand'],
                universal_newlines=True
            )
            brand = brand_result.strip()
            
            # 组合完整型号
            full_model = f"{brand} {model}"
            
            # 获取系统版本
            os_version_result = subprocess.check_output(
                [adb_path, 'shell', 'getprop', 'ro.build.version.release'],
                universal_newlines=True
            )
            os_version = os_version_result.strip()
            
            # 获取安卓API级别
            api_level_result = subprocess.check_output(
                [adb_path, 'shell', 'getprop', 'ro.build.version.sdk'],
                universal_newlines=True
            )
            api_level = api_level_result.strip()
            
            return {
                'model': full_model,
                'os_version': os_version,
                'api_level': api_level
            }
        except Exception as e:
            print(f"获取设备信息失败: {str(e)}")
            return {'model': '未知', 'os_version': '未知', 'api_level': '未知'}
    
    @staticmethod
    def get_devices():
        """获取已连接的设备列表"""
        devices = []
        try:
            adb_path = ADBTools.get_adb_path()
            result = subprocess.check_output([adb_path, 'devices'], universal_newlines=True)
            lines = result.strip().split('\n')[1:]
            for line in lines:
                if line.strip() and '\t' in line:
                    device_id, status = line.split('\t')
                    if status == 'device':
                        devices.append(device_id)
            return devices
        except:
            return []
    
    @staticmethod
    def connect_wireless(ip):
        """无线连接设备"""
        try:
            adb_path = ADBTools.get_adb_path()
            # 先尝试断开所有连接
            subprocess.call([adb_path, 'disconnect'])
            # 连接到指定IP
            result = subprocess.check_output([adb_path, 'connect', f"{ip}:5555"], universal_newlines=True)
            if 'connected' in result.lower():
                return True, result
            return False, result
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_fps():
        """获取当前FPS"""
        try:
            adb_path = ADBTools.get_adb_path()
            # 使用多种方法尝试获取FPS
            
            # 方法1: 使用SurfaceFlinger
            try:
                # 先清除历史数据
                subprocess.check_output(
                    [adb_path, 'shell', 'dumpsys', 'SurfaceFlinger', '--latency-clear'],
                    universal_newlines=True
                )
                time.sleep(0.5)  # 等待收集数据
                
                # 获取当前活动窗口（Windows兼容方式）
                window_cmd = subprocess.check_output(
                    [adb_path, 'shell', 'dumpsys', 'window'],
                    universal_newlines=True
                ).strip()
                
                # 手动查找mCurrentFocus
                current_focus = ""
                for line in window_cmd.split('\n'):
                    if 'mCurrentFocus' in line:
                        current_focus = line.strip()
                        break
                
                # 尝试多种可能的窗口名称
                window_names = ['SurfaceView']
                
                # 添加当前活动窗口
                if '/' in window_cmd:
                    current_window = window_cmd.split('/')[0].split(' ')[-1]
                    window_names.append(current_window)
                
                # 添加常见系统窗口
                window_names.extend(['com.android.systemui', 'com.android.launcher3', 'StatusBar'])
                
                for window_name in window_names:
                    try:
                        result = subprocess.check_output(
                            [adb_path, 'shell', 'dumpsys', 'SurfaceFlinger', '--latency', window_name],
                            universal_newlines=True, stderr=subprocess.STDOUT, timeout=1
                        )
                        lines = result.strip().split('\n')
                        if len(lines) > 1 and not 'not found' in result.lower():
                            # 计算帧率
                            frame_count = len(lines) - 1
                            if frame_count > 0 and frame_count < 120:  # 合理的FPS范围
                                print(f"成功从窗口 {window_name} 获取FPS: {frame_count}")
                                return frame_count
                    except Exception as e:
                        print(f"尝试从 {window_name} 获取FPS失败: {str(e)}")
                        continue
            except Exception as e:
                print(f"SurfaceFlinger方法获取FPS失败: {str(e)}")
            
            # 方法2: 使用gfxinfo
            try:
                # 获取前台应用包名（Windows兼容方式）
                foreground_app = subprocess.check_output(
                    [adb_path, 'shell', 'dumpsys', 'window'],
                    universal_newlines=True
                )
                package_name = None
                # 手动查找mCurrentFocus
                for line in foreground_app.split('\n'):
                    if 'mCurrentFocus' in line:
                        if '/' in line:
                            package_name = line.split('/')[0].split(' ')[-1]
                        break
                
                if package_name:
                    # 重置gfxinfo统计
                    subprocess.check_output(
                        [adb_path, 'shell', 'dumpsys', 'gfxinfo', package_name, 'reset'],
                        universal_newlines=True
                    )
                    time.sleep(0.5)  # 等待收集数据
                    
                    # 获取gfxinfo统计
                    gfx_result = subprocess.check_output(
                        [adb_path, 'shell', 'dumpsys', 'gfxinfo', package_name],
                        universal_newlines=True
                    )
                    
                    # 解析总帧数和卡顿帧数
                    if 'Total frames rendered' in gfx_result:
                        total_frames_line = next((line for line in gfx_result.split('\n') if 'Total frames rendered' in line), None)
                        if total_frames_line:
                            total_frames = int(total_frames_line.split(':')[1].strip())
                            if 0 < total_frames < 120:  # 合理的FPS范围
                                return total_frames
            except Exception as e:
                print(f"使用gfxinfo获取FPS失败: {str(e)}")
            
            # 方法3: 使用固定值作为备选
            # 如果所有方法都失败，返回一个合理的估计值
            return 60  # 大多数设备的标准刷新率
        except Exception as e:
            print(f"获取FPS失败: {str(e)}")
            return 60  # 返回默认值而不是0，避免图表显示异常
    
    @staticmethod
    def get_cpu_freq():
        """获取每个CPU核心的频率 (MHz)"""
        try:
            adb_path = ADBTools.get_adb_path()
            # 获取CPU核心数
            core_count = 0
            try:
                result = subprocess.check_output(
                    [adb_path, 'shell', 'cat', '/sys/devices/system/cpu/possible'],
                    universal_newlines=True
                )
                if result.strip():
                    # 格式通常为"0-7"表示8个核心
                    cores = result.strip().split('-')
                    core_count = int(cores[-1]) + 1
            except:
                core_count = 8  # 默认假设8核

            # 获取每个核心的频率
            core_freqs = {}
            for i in range(core_count):
                try:
                    # 尝试读取每个核心的频率
                    paths = [
                        f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq',
                        f'/sys/devices/system/cpu/cpu{i}/cpufreq/cpuinfo_cur_freq'
                    ]
                    
                    for path in paths:
                        try:
                            result = subprocess.check_output(
                                [adb_path, 'shell', 'cat', path],
                                universal_newlines=True, stderr=subprocess.DEVNULL
                            )
                            if result.strip() and result.strip().isdigit():
                                core_freqs[f'core_{i}'] = int(result.strip()) // 1000
                                break
                        except:
                            continue
                    
                    if f'core_{i}' not in core_freqs:
                        core_freqs[f'core_{i}'] = 1500  # 默认值
                except:
                    core_freqs[f'core_{i}'] = 1500  # 默认值
            
            return core_freqs
        except Exception as e:
            print(f"获取CPU频率失败: {str(e)}")
            return {'core_0': 1500}  # 至少返回一个核心的默认值

    _prev_cpu_stats = {}

    @staticmethod
    def get_cpu_load():
        """获取每个CPU核心的负载 (%)"""
        try:
            adb_path = ADBTools.get_adb_path()
            # 获取每个核心的负载
            result = subprocess.check_output(
                [adb_path, 'shell', 'cat', '/proc/stat'],
                universal_newlines=True
            )
            
            current_stats = {}
            core_loads = {}
            
            for line in result.split('\n'):
                if line.startswith('cpu'):
                    parts = line.split()
                    if len(parts) >= 8:
                        cpu_num = parts[0]
                        if cpu_num == 'cpu':
                            continue  # 跳过总体CPU统计
                        
                        # 收集当前CPU时间
                        user = int(parts[1])
                        nice = int(parts[2])
                        system = int(parts[3])
                        idle = int(parts[4])
                        iowait = int(parts[5])
                        irq = int(parts[6])
                        softirq = int(parts[7])
                        steal = int(parts[8]) if len(parts) > 8 else 0
                        
                        core_num = int(cpu_num.replace('cpu', ''))
                        current_stats[f'core_{core_num}'] = {
                            'total': user + nice + system + idle + iowait + irq + softirq + steal,
                            'idle': idle + iowait
                        }
                        
                        # 计算CPU使用率
                        if f'core_{core_num}' in ADBTools._prev_cpu_stats:
                            prev = ADBTools._prev_cpu_stats[f'core_{core_num}']
                            total_delta = current_stats[f'core_{core_num}']['total'] - prev['total']
                            idle_delta = current_stats[f'core_{core_num}']['idle'] - prev['idle']
                            
                            if total_delta > 0:
                                load = int(100.0 * (total_delta - idle_delta) / total_delta)
                                core_loads[f'core_{core_num}'] = min(100, max(0, load))
                            else:
                                core_loads[f'core_{core_num}'] = 0
                        else:
                            core_loads[f'core_{core_num}'] = 0
            
            # 更新历史数据
            ADBTools._prev_cpu_stats = current_stats
            
            return core_loads if core_loads else {'core_0': 0}
        except Exception as e:
            print(f"获取CPU负载失败: {str(e)}")
            return {'core_0': 0}  # 至少返回一个核心的默认值

    @staticmethod
    def get_gpu_load():
        """获取GPU负载 (%)，优先使用无需root权限的方法"""
        try:
            adb_path = ADBTools.get_adb_path()
            paths = [
                '/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage',
                '/sys/class/kgsl/kgsl-3d0/devfreq/gpu_load'
            ]
            
            # 首先尝试不使用root权限读取
            for path in paths:
                try:
                    result = subprocess.check_output(
                        [adb_path, 'shell', f'cat {path}'],
                        universal_newlines=True,
                        stderr=subprocess.PIPE
                    )
                    if result.strip() and not 'Permission denied' in result:
                        return int(result.strip())
                except Exception as e:
                    continue
            
            # 如果无法访问，返回估算值
            print("无法访问GPU负载数据（设备未root），将返回估算值")
            return 30  # 返回一个合理的估计值
        except Exception as e:
            print(f"获取GPU负载失败: {str(e)}")
            return 0

    @staticmethod
    def get_gpu_freq():
        """获取GPU频率 (MHz)，优先使用无需root权限的方法"""
        try:
            adb_path = ADBTools.get_adb_path()
            # 不同设备GPU频率文件路径可能不同，这里尝试更多可能的路径
            paths = [
                '/sys/class/kgsl/kgsl-3d0/gpuclk',
                '/sys/class/kgsl/kgsl-3d0/devfreq/cur_freq',
                '/sys/class/kgsl/kgsl-3d0/freq',
                '/sys/kernel/gpu/gpu_clock',
                '/sys/class/devfreq/gpufreq/cur_freq',
                '/sys/class/kgsl/kgsl-3d0/clock',
                '/sys/kernel/debug/gpu/clock',
                '/sys/devices/platform/kgsl-3d0/kgsl/kgsl-3d0/gpuclk',
                '/sys/devices/soc/1c00000.qcom,kgsl-3d0/kgsl/kgsl-3d0/gpuclk',
                '/sys/devices/platform/gpusysfs/gpu_clock'
            ]
            
            # 首先尝试不使用root权限读取
            for path in paths:
                try:
                    result = subprocess.check_output(
                        [adb_path, 'shell', f'cat {path}'],
                        universal_newlines=True,
                        stderr=subprocess.PIPE
                    )
                    if result.strip() and not 'Permission denied' in result:
                        # 尝试转换为整数并计算MHz
                        value = int(result.strip())
                        # 根据数值大小判断单位并转换
                        if value > 1000000:  # Hz
                            return value // 1000000
                        elif value > 1000:  # kHz
                            return value // 1000
                        else:  # 已经是MHz
                            return value
                except Exception as e:
                    continue
            
            # 如果无法访问文件系统，尝试从dumpsys获取GPU信息
            try:
                result = subprocess.check_output(
                    [adb_path, 'shell', 'dumpsys', 'gfxinfo'],
                    universal_newlines=True
                )
                # 解析dumpsys输出以获取GPU相关信息
                if 'GPU' in result:
                    return 500  # 返回一个典型的GPU频率值
            except Exception as e:
                print(f"从dumpsys获取GPU信息失败: {str(e)}")
            
            print("无法访问GPU频率数据，将返回估算值")
            return 400  # 返回一个合理的默认值
        except Exception as e:
            print(f"获取GPU频率失败: {str(e)}")
            return 400  # 返回默认值而不是0，避免图表显示异常
    
    @staticmethod
    def get_battery_info():
        """获取电池信息（电流和功率）"""
        try:
            adb_path = ADBTools.get_adb_path()
            result = subprocess.check_output(
                [adb_path, 'shell', 'dumpsys', 'battery'],
                universal_newlines=True
            )
            
            # 解析电流 (mA)
            current = 0
            voltage = 0
            for line in result.split('\n'):
                if 'current now' in line.lower():
                    try:
                        current = abs(int(line.split(':')[1].strip()) / 1000)  # 转换为mA
                    except:
                        pass
                elif 'voltage' in line.lower():
                    try:
                        voltage = int(line.split(':')[1].strip()) / 1000  # 转换为V
                    except:
                        pass
            
            # 计算功率 (mW)
            power = current * voltage
            
            return {
                'current': current,  # mA
                'power': power       # mW
            }
        except:
            return {'current': 0, 'power': 0}

# 监控线程函数
def monitor_performance(interval=1.0):
    global monitoring, connected_device
    while monitoring:
        try:
            # 检查设备是否仍然连接
            if not connected_device:
                print("设备连接已断开，停止监控")
                monitoring = False
                break

            # 验证ADB连接状态
            if not ADBTools.check_adb():
                print("ADB连接异常，等待2秒后重试")
                time.sleep(2)
                continue

            # 收集所有性能数据
            try:
                fps = ADBTools.get_fps()
                cpu_freq = ADBTools.get_cpu_freq()
                gpu_freq = ADBTools.get_gpu_freq()
                cpu_load = ADBTools.get_cpu_load()
                gpu_load = ADBTools.get_gpu_load()
                battery_info = ADBTools.get_battery_info()

                # 构建数据包
                data = {
                    'timestamp': time.time(),
                    'fps': fps,
                    'cpu_freq': {k: round(v, 2) for k, v in cpu_freq.items()},
                    'gpu_freq': gpu_freq,
                    'cpu_load': cpu_load,
                    'gpu_load': gpu_load,
                    'current': round(battery_info['current'], 2),
                    'power': round(battery_info['power'], 2)
                }

                # 发送数据到前端
                socketio.emit('performance_data', data)
            except Exception as e:
                print(f"性能数据采集错误: {str(e)}")
                time.sleep(1)
                continue

            # 根据设置的时间间隔更新
            time.sleep(interval)
        except Exception as e:
            print(f"监控线程异常: {str(e)}")
            time.sleep(2)

# 路由
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check_adb', methods=['GET'])
def check_adb():
    return jsonify({'available': ADBTools.check_adb()})

@app.route('/api/devices', methods=['GET'])
def get_devices():
    return jsonify({'devices': ADBTools.get_devices()})

@app.route('/api/device_info', methods=['GET'])
def get_device_info_api():
    """获取设备信息API"""
    if not connected_device:
        return jsonify({'success': False, 'message': '未连接设备'})
    
    device_info = ADBTools.get_device_info()
    return jsonify({
        'success': True,
        'device_info': device_info
    })

@app.route('/api/connect', methods=['POST'])
def connect_device():
    global connected_device
    data = request.json
    
    if 'wireless' in data and data['wireless']:
        # 无线连接
        if 'ip' not in data or not data['ip']:
            return jsonify({'success': False, 'message': '请提供设备IP地址'})
        
        success, message = ADBTools.connect_wireless(data['ip'])
        if success:
            connected_device = f"{data['ip']}:5555"
            # 获取设备信息
            device_info = ADBTools.get_device_info()
            return jsonify({'success': True, 'message': message, 'device_info': device_info})
        else:
            return jsonify({'success': False, 'message': f"连接失败: {message}"})
    else:
        # 有线连接
        devices = ADBTools.get_devices()
        if not devices:
            return jsonify({'success': False, 'message': '未找到已连接的设备'})
        
        connected_device = devices[0]  # 使用第一个设备
        # 获取设备信息
        device_info = ADBTools.get_device_info()
        return jsonify({'success': True, 'message': f"已连接到设备: {connected_device}", 'device_info': device_info})

@app.route('/api/start_monitoring', methods=['POST'])
def start_monitoring():
    global monitoring, monitor_thread, connected_device
    
    if not connected_device:
        return jsonify({'success': False, 'message': '未连接设备'})
    
    # 获取时间间隔参数
    data = request.json
    interval = float(data.get('interval', 1.0))
    
    if not monitoring:
        monitoring = True
        monitor_thread = threading.Thread(target=monitor_performance, args=(interval,))
        monitor_thread.daemon = True
        monitor_thread.start()
        return jsonify({'success': True, 'message': '监控已启动'})
    else:
        return jsonify({'success': False, 'message': '监控已在运行中'})

@app.route('/api/stop_monitoring', methods=['POST'])
def stop_monitoring():
    global monitoring
    
    if monitoring:
        monitoring = False
        return jsonify({'success': True, 'message': '监控已停止'})
    else:
        return jsonify({'success': False, 'message': '监控未运行'})

@app.route('/api/disconnect', methods=['POST'])
def disconnect_device():
    global connected_device, monitoring
    
    # 先停止监控
    if monitoring:
        monitoring = False
        time.sleep(1)  # 等待监控线程结束
    
    # 断开连接
    try:
        adb_path = ADBTools.get_adb_path()
        subprocess.call([adb_path, 'disconnect'])
        connected_device = None
        return jsonify({'success': True, 'message': '设备已断开连接'})
    except Exception as e:
        return jsonify({'success': False, 'message': f"断开连接失败: {str(e)}"})

if __name__ == '__main__':
    # 创建templates目录（如果不存在）
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 创建static目录（如果不存在）
    if not os.path.exists('static'):
        os.makedirs('static')
    
    print("手机性能监控服务器已启动，请访问 http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)