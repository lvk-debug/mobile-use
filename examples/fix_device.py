import time

import uiautomator2 as u2

d = u2.connect('4cb7aa51')

# 检查屏幕是否亮着
print('screen on:', d.info.get('screenOn'))

# 尝试唤醒屏幕
if not d.info.get('screenOn'):
    print('waking up screen...')
    d.press('power')
    time.sleep(1)

# 检查当前应用
print('current app:', d.app_current())

# 尝试解锁（上滑）
print('trying to unlock...')
d.swipe_ext('up')
time.sleep(0.5)

print('current app after unlock:', d.app_current())

# 测试点击
print('testing click at center...')
w, h = d.window_size()
d.click(w // 2, h // 2)
print('click done!')
