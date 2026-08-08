import subprocess

import uiautomator2 as u2

ADB = r'D:\Program Files (x86)\platform-tools\adb.exe'

d = u2.connect('4cb7aa51')
serial = '4cb7aa51'

# 获取屏幕尺寸
w, h = d.window_size()
print(f'screen size: {w}x{h}')

# 使用 adb shell input tap
cx, cy = w // 2, h // 2
print(f'testing adb shell input tap {cx} {cy}')
subprocess.run([ADB, '-s', serial, 'shell', 'input', 'tap', str(cx), str(cy)])
print('adb tap done!')

# 测试 adb shell input swipe
print('testing adb shell input swipe')
subprocess.run([
    ADB, '-s', serial, 'shell', 'input', 'swipe',
    str(cx), str(h * 3 // 4), str(cx), str(h // 4), '500'
])
print('adb swipe done!')
