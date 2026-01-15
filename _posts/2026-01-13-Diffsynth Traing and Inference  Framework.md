---
layout:     post
title:      "Diffsynth Traing and Inference  Framework"
subtitle:   "share experience"
active: journal
image:
  feature: "pc012.jpg"
date:       2026-01-13
header-img: "img/postcover/pc012.jpg"
tags: [Diffusion,Training]
categories: [Research]
comments: true
---

## 前言

本文章作为自己这三天从0开始到已经可以自由改 Diffsynth 框架各个部分的学习记录。

通常一个完整的模型训练流程需要数据，模型，训练模块，训推Pipeline和一些其他的超参数或者优化等其他部分，因为我最近在做virtual-tryon video 生成，我将以这个task为例，按照数据准备、模型架构的修改、训推pipeline如何构建、还有一些其他的参数和框架的小设计四个方面介绍。

## 数据

Diffsynth 框架的数据处理部分，主要使用 diffsyhth.core.data 目录下提供的一系列数据算子，包括如下：

### 算子介绍

- 数据格式转换算子
  - ToInt: 转换为 int 格式
  - ToFloat: 转换为 float 格式
  - ToStr: 转换为 str 格式
  - ToList: 转换为列表格式，以列表包裹此数据
  - ToAbsolutePath: 将相对路径转换为绝对路径

- 文件加载算子
  - LoadImage: 读取图片文件
  - LoadVideo: 读取视频文件
  - LoadAudio: 读取音频文件
  - LoadGIF: 读取 GIF 文件
  - LoadTorchPickle: 读取由 torch.save 保存的二进制文件【该算子可能导致二进制文件中的代码注入攻击，请谨慎使用！】

  
- 媒体文件处理算子
  - ImageCropAndResize: 对图像进行裁剪和拉伸
  
- Meta 算子
  - SequencialProcess: 将序列中的每个数据路由到一个算子
  - RouteByExtensionName: 按照文件扩展名路由到特定算子
  - RouteByType: 按照数据类型路由到特定算子

### 算子使用
数据算子之间以 >> 符号连接形成数据处理流水线，例如：

```python
from diffsynth.core.data.operators import *

data = "image.jpg"
data_pipeline = ToAbsolutePath(base_path="/data") >> LoadImage() >> ImageCropAndResize(max_pixels=512*512)
data = data_pipeline(data)
```

在经过每个算子后，数据被依次处理，注意得到的是 PIL 文件或者文件List，在后续的模型处理unit中会对这些PIL 处理成 tensor。

- `ToAbsolutePath(base_path="/data")`: `"/data/image.jpg"`
- `LoadImage()`: `<PIL.Image.Image image mode=RGB size=1024x1024 at 0x7F8E7AAEFC10>`
- `ImageCropAndResize(max_pixels=512*512)`: `<PIL.Image.Image image mode=RGB size=512x512 at 0x7F8E7A936F20>`

组合出功能完备的数据流水线，例如通用数据集的默认视频数据算子为

```python
RouteByType(operator_map=[
    (str, ToAbsolutePath(base_path) >> RouteByExtensionName(operator_map=[
        (("jpg", "jpeg", "png", "webp"), LoadImage() >> ImageCropAndResize(height, width, max_pixels, height_division_factor, width_division_factor) >> ToList()),
        (("gif",), LoadGIF(
            num_frames, time_division_factor, time_division_remainder,
            frame_processor=ImageCropAndResize(height, width, max_pixels, height_division_factor, width_division_factor),
        )),
        (("mp4", "avi", "mov", "wmv", "mkv", "flv", "webm"), LoadVideo(
            num_frames, time_division_factor, time_division_remainder,
            frame_processor=ImageCropAndResize(height, width, max_pixels, height_division_factor, width_division_factor),
        )),
    ])),
])

```
它包含如下逻辑：
- 如果是 str 类型的数据
  - 如果是 "jpg", "jpeg", "png", "webp" 类型文件
    - 加载这张图片
    - 裁剪并缩放到特定分辨率
    - 打包进列表，视为单帧视频
  - 如果是 "gif" 类型文件
    - 加载 gif 文件内容
    - 将每一帧裁剪和缩放到特定分辨率
  - 如果是 "mp4", "avi", "mov", "wmv", "mkv", "flv", "webm" 类型文件
    - 加载 gif 文件内容
    - 将每一帧裁剪和缩放到特定分辨率
- 如果不是 str 类型的数据，报错

### 元数据
数据集的 metadata_path 指向元数据文件，支持 csv、json、jsonl 格式，以下提供了样例，主要用来提供数据集的加载路径名和一些补充的信息

我一般使用jsonl格式，json和csv也可以

```python
{"image": "image_1.jpg", "prompt": "a dog"}
{"image": "image_2.jpg", "prompt": "a cat"}
```

### Virtual-TryOn 数据样例

对于一个数据集我们先看一下我们的matedata的格式：

```
{"x": "048589_0.jpg", "cloth": "048589_0.jpg", "category": "dresscode", "type": "image", "caption": "The garment is a black T-shirt featuring a crew neck and short sleeves. The fabric appears to be a smooth, solid black, suggesting a simple yet versatile design. There is a small, white tag at the neckline, which likely contains brand information or care instructions. The T-shirt has a relaxed fit, with slightly loose shoulders and a longer body that extends past the hips, giving it a casual and comfortable look. The overall style is minimalist, with no additional patterns, logos, or embellishments, making it suitable for various occasions.", "width": 768, "height": 1024}
{"x": "049262_0.jpg", "cloth": "049262_0.jpg", "category": "viton", "type": "image", "caption": "The garment is a black T-shirt featuring a graphic design that prominently displays a stylized speaker with concentric circles and a central circular element resembling a face. The design is surrounded by abstract, swirling lines in white and light blue, creating a dynamic and energetic effect. Above the graphic, the text \"ARMANI EXCHANGE\" is printed in a clean, sans-serif font, followed by \"SOUNDS GOOD\" in a smaller size beneath it. The neckline of the T-shirt is a contrasting light blue, adding a subtle pop of color to the otherwise monochromatic design. The overall style of the T-shirt suggests a casual yet modern aesthetic", "width": 768, "height": 1024}
{"x": "049357_0.jpg", "cloth": "049357_0.jpg", "category": "vivid", "type": "video", "caption": "The garment is a blouse featuring a vibrant floral print. The flowers are predominantly purple with yellow centers, set against a white background. The leaves are a deep green, adding contrast to the design. The blouse has a loose, off-the-shoulder style with puffed sleeves that taper towards the wrist. The fabric appears to be lightweight and flowy, suggesting a comfortable and airy feel. The neckline is elasticated, providing a snug fit around the neck. There are no visible texts or graphics other than the floral pattern itself.", "width": 768, "height": 1024}
```

我们的数据有三个categories（dresscode、viton、vivid），其中vivid是video数据，其他另外两个是image数据，因此，根据jsonl的不同数据categories我们要加载不同的目录。并且由于数据类型不同，我们还需要两个加载数据的算子流（video、image）。最后，我们的这个模型要多阶段训练，第一阶段只训练两个image数据集，第二个阶段训练video数据集，所以我们的数据集要加一个stage来控制加载数据的类型。

```python
class TryOnDataset(torch.utils.data.Dataset):
  def __init__(
      self,
      dataset_root,          
      metadata_path,          
      stage="image",  # 过滤这个阶段需要哪个数据
      split="train",          
      height=480,
      width=832,
      num_frames=49,          
      repeat=1,
      load_from_cache=False
  ):
    self.image_op = (
        LoadImage() 
        >> ImageCropAndResize(height, width) 
        >> ToList() 
    )

    self.video_op = LoadVideo(
        num_frames=self.num_frames,
        frame_processor=ImageCropAndResize(height, width) 
    )
    ...
```

最后，其实可以把两个阶段需要的jsonl进行拆分，不同阶段加载不同的metadata。对于不同类型的数据，可以用RouteByExtensionName对数据进行处理。

## 训推pipeline

