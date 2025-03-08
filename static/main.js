// 全局变量
let socket;
let performanceChart;
let chartType = 'fps';
let isConnected = false;
let isMonitoring = false;
let performanceData = [];

// 初始化页面
document.addEventListener('DOMContentLoaded', function() {
    // 检查ADB是否可用
    checkADB();
    
    // 初始化图表
    initChart();
    
    // 初始化Socket.IO连接
    initSocketIO();
    
    // 初始化事件监听器
    initEventListeners();
});

// 检查ADB是否可用
function checkADB() {
    fetch('/api/check_adb')
        .then(response => response.json())
        .then(data => {
            if (!data.available) {
                alert('警告: ADB工具不可用，请确保已安装ADB并添加到系统环境变量中。');
            }
        })
        .catch(error => {
            console.error('检查ADB错误:', error);
            alert('无法检查ADB状态，请确保服务器正在运行。');
        });
}

// 初始化Socket.IO连接
function initSocketIO() {
    console.log('正在初始化Socket.IO连接...');
    // 明确指定连接URL和选项，强制使用WebSocket传输
    socket = io(window.location.origin, {
        transports: ['websocket'],  // 只使用WebSocket传输
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        timeout: 20000,
        forceNew: true
    });
    
    // 添加连接事件处理
    socket.on('connect', function() {
        console.log('Socket.IO连接成功，ID:', socket.id);
    });
    
    socket.on('connect_error', function(error) {
        console.error('Socket.IO连接错误:', error);
        alert('WebSocket连接失败，请检查网络连接或刷新页面重试。');
    });
    
    socket.on('disconnect', function(reason) {
        console.log('Socket.IO连接断开:', reason);
    });
    
    // 监听性能数据
    socket.on('performance_data', function(data) {
        console.log('收到性能数据:', data);
        updateMetrics(data);
        updateChart(data);
        performanceData.push(data);
        document.getElementById('dataPointCount').textContent = performanceData.length;
    });
}

// 初始化事件监听器
function initEventListeners() {
    // 连接类型切换
    document.querySelectorAll('input[name="connectionType"]').forEach(radio => {
        radio.addEventListener('change', function() {
            const wirelessOptions = document.getElementById('wirelessOptions');
            if (this.value === 'wireless') {
                wirelessOptions.style.display = 'block';
            } else {
                wirelessOptions.style.display = 'none';
            }
        });
    });
    
    // 连接按钮
    document.getElementById('connectBtn').addEventListener('click', connectDevice);
    
    // 断开连接按钮
    document.getElementById('disconnectBtn').addEventListener('click', disconnectDevice);
    
    // 开始监控按钮
    document.getElementById('startMonitoringBtn').addEventListener('click', startMonitoring);
    
    // 停止监控按钮
    document.getElementById('stopMonitoringBtn').addEventListener('click', stopMonitoring);
    
    // 导出数据按钮
    document.getElementById('exportBtn').addEventListener('click', exportData);
    
    // 图表类型切换按钮
    document.querySelectorAll('.btn-group button').forEach(button => {
        button.addEventListener('click', function() {
            // 移除所有按钮的active类
            document.querySelectorAll('.btn-group button').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // 添加当前按钮的active类
            this.classList.add('active');
            
            // 更新图表类型
            chartType = this.getAttribute('data-chart');
            updateChartType();
        });
    });
}

// 初始化图表
function initChart() {
    const ctx = document.getElementById('performanceChart').getContext('2d');
    
    performanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'FPS',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '时间'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '值'
                    },
                    beginAtZero: true
                }
            },
            animation: {
                duration: 0 // 禁用动画以提高性能
            }
        }
    });
}

// 更新图表类型
function updateChartType() {
    // 清除现有数据
    performanceChart.data.datasets[0].data = [];
    performanceChart.data.labels = [];
    
    // 设置图表标题和颜色
    switch(chartType) {
        case 'fps':
            performanceChart.data.datasets[0].label = 'FPS';
            performanceChart.data.datasets[0].borderColor = 'rgb(75, 192, 192)';
            performanceChart.options.scales.y.title.text = '帧/秒';
            break;
        case 'cpu':
            performanceChart.data.datasets[0].label = 'CPU负载';
            performanceChart.data.datasets[0].borderColor = 'rgb(255, 99, 132)';
            performanceChart.options.scales.y.title.text = '%';
            break;
        case 'gpu':
            performanceChart.data.datasets[0].label = 'GPU负载';
            performanceChart.data.datasets[0].borderColor = 'rgb(54, 162, 235)';
            performanceChart.options.scales.y.title.text = '%';
            break;
        case 'power':
            performanceChart.data.datasets[0].label = '功率';
            performanceChart.data.datasets[0].borderColor = 'rgb(255, 159, 64)';
            performanceChart.options.scales.y.title.text = 'mW';
            break;
    }
    
    // 重新填充数据
    performanceData.forEach(data => {
        const time = new Date(data.timestamp * 1000).toLocaleTimeString();
        performanceChart.data.labels.push(time);
        
        switch(chartType) {
            case 'fps':
                performanceChart.data.datasets[0].data.push(data.fps);
                break;
            case 'cpu':
                const avgCpuLoad = Object.values(data.cpu_load).reduce((a, b) => a + b, 0) / Object.keys(data.cpu_load).length;
                performanceChart.data.datasets[0].data.push(avgCpuLoad);
                break;
            case 'gpu':
                performanceChart.data.datasets[0].data.push(data.gpu_load);
                break;
            case 'power':
                performanceChart.data.datasets[0].data.push(data.power);
                break;
        }
    });
    
    // 更新图表
    performanceChart.update();
}

// 更新指标显示
function updateMetrics(data) {
    document.getElementById('fpsValue').textContent = data.fps;
    document.getElementById('cpuFreqValue').textContent = Object.values(data.cpu_freq).reduce((a, b) => a + b, 0) / Object.keys(data.cpu_freq).length;
    document.getElementById('gpuFreqValue').textContent = data.gpu_freq;
    document.getElementById('cpuLoadValue').textContent = Object.values(data.cpu_load).reduce((a, b) => a + b, 0) / Object.keys(data.cpu_load).length;
    document.getElementById('gpuLoadValue').textContent = data.gpu_load;
    document.getElementById('currentValue').textContent = data.current + ' mA';
    document.getElementById('powerValue').textContent = data.power;

    // 更新CPU核心状态
    const cpuCoresContainer = document.getElementById('cpuCoresContainer');
    cpuCoresContainer.innerHTML = '';
    
    // 获取所有核心编号并排序
    const coreNumbers = Object.keys(data.cpu_freq)
        .map(key => parseInt(key.replace('core_', '')))
        .sort((a, b) => a - b);

    // 为每个核心创建显示卡片
    coreNumbers.forEach(coreNum => {
        const coreKey = `core_${coreNum}`;
        const coreFreq = data.cpu_freq[coreKey];
        const coreLoad = data.cpu_load[coreKey];

        const coreCard = document.createElement('div');
        coreCard.className = 'core-card';
        coreCard.style.width = '120px';
        coreCard.style.margin = '5px';
        coreCard.style.padding = '10px';
        coreCard.style.border = '1px solid #dee2e6';
        coreCard.style.borderRadius = '5px';
        coreCard.style.textAlign = 'center';

        coreCard.innerHTML = `
            <div style="font-size: 12px; color: #6c757d;">核心 ${coreNum}</div>
            <div style="font-size: 14px; font-weight: bold;">${coreFreq} MHz</div>
            <div style="font-size: 14px; font-weight: bold;">${coreLoad}%</div>
        `;

        cpuCoresContainer.appendChild(coreCard);
    });
}

// 更新图表数据
function updateChart(data) {
    // 限制显示的数据点数量，保持最新的100个点
    if (performanceChart.data.labels.length > 100) {
        performanceChart.data.labels.shift();
        performanceChart.data.datasets[0].data.shift();
    }
    
    // 添加新数据点
    const time = new Date(data.timestamp * 1000).toLocaleTimeString();
    performanceChart.data.labels.push(time);
    
    switch(chartType) {
        case 'fps':
            performanceChart.data.datasets[0].data.push(data.fps);
            break;
        case 'cpu':
            performanceChart.data.datasets[0].data.push(data.cpu_load);
            break;
        case 'gpu':
            performanceChart.data.datasets[0].data.push(data.gpu_load);
            break;
        case 'power':
            performanceChart.data.datasets[0].data.push(data.power);
            break;
    }
    
    // 更新图表显示
    performanceChart.update();
}

// 连接设备
function connectDevice() {
    const isWireless = document.getElementById('wirelessConnection').checked;
    let data = { wireless: isWireless };
    
    if (isWireless) {
        const deviceIP = document.getElementById('deviceIP').value.trim();
        if (!deviceIP) {
            alert('请输入设备IP地址');
            return;
        }
        data.ip = deviceIP;
    }
    
    // 发送连接请求
    fetch('/api/connect', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            isConnected = true;
            updateConnectionStatus(true, data.message);
            document.getElementById('connectBtn').disabled = true;
            document.getElementById('disconnectBtn').disabled = false;
            document.getElementById('startMonitoringBtn').disabled = false;
            document.getElementById('stopMonitoringBtn').disabled = true;
            document.getElementById('exportBtn').disabled = false;
        } else {
            alert('连接失败: ' + data.message);
        }
    })
    .catch(error => {
        console.error('连接错误:', error);
        alert('连接请求失败，请检查服务器状态。');
    });
}

// 断开设备连接
function disconnectDevice() {
    // 如果正在监控，先停止监控
    if (isMonitoring) {
        stopMonitoring();
    }
    
    // 发送断开连接请求
    fetch('/api/disconnect', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            isConnected = false;
            updateConnectionStatus(false, data.message);
            document.getElementById('connectBtn').disabled = false;
            document.getElementById('disconnectBtn').disabled = true;
            document.getElementById('startMonitoringBtn').disabled = true;
            document.getElementById('stopMonitoringBtn').disabled = true;
            document.getElementById('exportBtn').disabled = true;
        } else {
            alert('断开连接失败: ' + data.message);
        }
    })
    .catch(error => {
        console.error('断开连接错误:', error);
        alert('断开连接请求失败，请检查服务器状态。');
    });
}

// 开始监控
function startMonitoring() {
    if (!isConnected) {
        alert('请先连接设备');
        return;
    }
    
    // 发送开始监控请求
    const interval = document.getElementById('intervalSelect').value;
    fetch('/api/start_monitoring', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ interval: parseFloat(interval) })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            isMonitoring = true;
            updateMonitoringStatus(true, data.message);
            document.getElementById('startMonitoringBtn').disabled = true;
            document.getElementById('stopMonitoringBtn').disabled = false;
            
            // 清空历史数据
            performanceData = [];
            document.getElementById('dataPointCount').textContent = '0';
            
            // 重置图表
            performanceChart.data.labels = [];
            performanceChart.data.datasets[0].data = [];
            performanceChart.update();
        } else {
            alert('启动监控失败: ' + data.message);
        }
    })
    .catch(error => {
        console.error('启动监控错误:', error);
        alert('启动监控请求失败，请检查服务器状态。');
    });
}

// 停止监控
function stopMonitoring() {
    // 发送停止监控请求
    fetch('/api/stop_monitoring', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            isMonitoring = false;
            updateMonitoringStatus(false, data.message);
            document.getElementById('startMonitoringBtn').disabled = false;
            document.getElementById('stopMonitoringBtn').disabled = true;
        } else {
            alert('停止监控失败: ' + data.message);
        }
    })
    .catch(error => {
        console.error('停止监控错误:', error);
        alert('停止监控请求失败，请检查服务器状态。');
    });
}

// 导出数据
function exportData() {
    if (performanceData.length === 0) {
        alert('没有可导出的数据');
        return;
    }
    
    // 准备CSV数据
    let csvContent = '时间戳,FPS,CPU平均负载,GPU负载,功率(mW)';
    
    // 添加CPU核心负载的表头
    const firstData = performanceData[0];
    const coreCount = Object.keys(firstData.cpu_load).length;
    for (let i = 0; i < coreCount; i++) {
        csvContent += `,CPU核心${i}负载(%)`;
    }
    csvContent += '\n';
    
    // 添加数据行
    performanceData.forEach(data => {
        const time = new Date(data.timestamp * 1000).toLocaleString();
        const cpuLoads = Object.values(data.cpu_load);
        const avgCpuLoad = (cpuLoads.reduce((a, b) => a + b, 0) / cpuLoads.length).toFixed(2);
        
        let row = [
            time,
            data.fps,
            avgCpuLoad,
            data.gpu_load,
            data.power
        ];
        
        // 添加每个CPU核心的负载数据
        cpuLoads.forEach(load => {
            row.push(load);
        });
        
        csvContent += row.join(',') + '\n';
    });
    
    // 创建并下载CSV文件
    const blob = new Blob([new Uint8Array([0xEF, 0xBB, 0xBF]), csvContent], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `性能数据_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

// 创建CSV内容
let csvContent = 'data:text/csv;charset=utf-8,';
csvContent += '时间戳,FPS,CPU频率(MHz),GPU频率(MHz),CPU负载(%),GPU负载(%),电流(mA),功率(mW)\n';

performanceData.forEach(data => {
    const time = new Date(data.timestamp * 1000).toLocaleString();
    csvContent += `${time},${data.fps},${data.cpu_freq},${data.gpu_freq},${data.cpu_load},${data.gpu_load},${data.current},${data.power}\n`;
});

// 创建下载链接
const encodedUri = encodeURI(csvContent);
const link = document.createElement('a');
link.setAttribute('href', encodedUri);
link.setAttribute('download', `性能数据_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.csv`);
document.body.appendChild(link);
link.click();
document.body.removeChild(link);

// 更新连接状态
function updateConnectionStatus(connected, message) {
    const statusElement = document.getElementById('connectionStatus');
    const deviceIdElement = document.getElementById('deviceId');
    const deviceInfoSection = document.getElementById('deviceInfoSection');
    const deviceModelElement = document.getElementById('deviceModel');
    const osVersionElement = document.getElementById('osVersion');
    const apiLevelElement = document.getElementById('apiLevel');
    
    if (connected) {
        statusElement.innerHTML = `<span class="status-indicator status-connected"></span> 已连接`;
        deviceIdElement.textContent = message.split(': ')[1] || '未知';
        
        // 获取设备信息
        fetch('/api/device_info')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.device_info) {
                    deviceModelElement.textContent = data.device_info.model || '-';
                    osVersionElement.textContent = data.device_info.os_version || '-';
                    apiLevelElement.textContent = data.device_info.api_level || '-';
                    deviceInfoSection.style.display = 'block';
                }
            })
            .catch(error => {
                console.error('获取设备信息错误:', error);
            });
    } else {
        statusElement.innerHTML = `<span class="status-indicator status-disconnected"></span> 未连接`;
        deviceIdElement.textContent = '-';
        deviceInfoSection.style.display = 'none';
    }
}

// 更新监控状态
function updateMonitoringStatus(monitoring, message) {
    const statusElement = document.getElementById('monitoringStatus');
    
    if (monitoring) {
        statusElement.innerHTML = `<span class="status-indicator status-monitoring"></span> 监控中`;
    } else {
        statusElement.innerHTML = `<span class="status-indicator status-disconnected"></span> 未监控`;
    }
}