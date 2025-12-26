import os
from PIL import Image

# 设置图片所在的文件夹路径 (根据你之前的截图，应该是这个路径)
# 如果脚本在仓库根目录，这里指向 img/slider/
folder_path = 'img/slider' 

# 需要处理的文件名列表
target_files = ['home02.jpg']

# 目标尺寸
new_size = (1080, 720)

print("-" * 30)
print(f"准备将图片调整为: {new_size}")
print("-" * 30)

for filename in target_files:
    file_path = os.path.join(folder_path, filename)
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
        continue
        
    try:
        # 打开图片
        with Image.open(file_path) as img:
            # 读取原始大小
            print(f"📄 文件: {filename}")
            print(f"   原始大小: {img.size}")
            
            # 执行缩放 (使用 LANCZOS 滤镜保持高质量)
            resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 直接覆盖保存原文件 (如果想保留原图，可以改个名保存)
            resized_img.save(file_path, quality=95)
            
            print(f"   ✅ 已调整为: {resized_img.size}")
            
    except Exception as e:
        print(f"   ❌ 处理出错: {e}")

print("-" * 30)
print("处理完成！请记得 git add, commit 和 push 更新到 GitHub。")