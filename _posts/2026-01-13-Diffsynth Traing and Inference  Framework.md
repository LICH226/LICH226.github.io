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

Diffsynth 框架的训推都用的是一个 pipeline，这样它的训练模块可以直接使用推理 pipeline，减少代码复杂度。
个人觉得，对于扩散模型的训练，应该先确定我们的 dit 主干网络需要哪些 condition，而condition则需要通过各个组件（unit）处理成各种需要的形式比如latent、clip embedding、dino embedding、T5 embedding。

Pipeline 的实现位于 diffsynth/pipelines，每个 Pipeline 包含以下必要的关键组件：

- init: 初始化，需要哪些 module vae？t5 embedding？clip？ 
- from_pretrained：加载模型，对于 vae t5 clip 这种直接用就可以，但是因为 Diffsynth 框架只提供了部分模型代码，所以个人觉得，对于一些该框架没有的模型（但是  huggingface 有的）可以在这个部分初始化，比如 dinov3 等。
- call：推理时的 pipeline，兼容 cfg 等参数
- units：用来把各个数据处理成想要的形式的组件
- model_fn：经过 unit 处理后的数据如何给 dit 主干网络，但其实大部分的模型直接把 inpit 输入给 dit 网络就可以了

### 模型加载

```diffsynth.core.loader``` 中有模型下载与加载相关的功能。远程加载不多赘述，因为基本都是下载到本地然后加载的。

#### 从本地路径加载模型
如果从本地路径加载模型，则需要填入 path：

```python
from diffsynth.core import ModelConfig

config = ModelConfig(path="models/DiffSynth-Studio/Qwen-Image-Blockwise-ControlNet-Canny/model.safetensors")
```
如果模型包含多个分片文件，以列表的形式输入即可：

```python
from diffsynth.core import ModelConfig

config = ModelConfig(path=[
    "models/Qwen/Qwen-Image/text_encoder/model-00001-of-00004.safetensors",
    "models/Qwen/Qwen-Image/text_encoder/model-00002-of-00004.safetensors",
    "models/Qwen/Qwen-Image/text_encoder/model-00003-of-00004.safetensors",
    "models/Qwen/Qwen-Image/text_encoder/model-00004-of-00004.safetensors"
])
```

#### 模型哈希
模型哈希是用于判断模型类型的，哈希值可通过 hash_model_file 获取：

```python
from diffsynth.core import hash_model_file

print(hash_model_file("models/DiffSynth-Studio/Qwen-Image-Blockwise-ControlNet-Canny/model.safetensors"))
```

也可计算多个模型文件的哈希值，等价于合并 state dict 后计算模型哈希值：

```python
from diffsynth.core import hash_model_file

print(hash_model_file([
    "models/Qwen/Qwen-Image/text_encoder/model-00001-of-00004.safetensors",
    "models/Qwen/Qwen-Image/text_encoder/model-00002-of-00004.safetensors",
    "models/Qwen/Qwen-Image/text_encoder/model-00003-of-00004.safetensors",
    "models/Qwen/Qwen-Image/text_encoder/model-00004-of-00004.safetensors"
]))
```
模型哈希值只与模型文件中 state dict 的 keys 和 tensor shape 有关，与模型参数的数值、文件保存时间等信息无关。在计算 .safetensors 格式文件的模型哈希值时，hash_model_file 是几乎瞬间完成的，无需读取模型的参数；但在计算 .bin、.pth、.ckpt 等二进制文件的模型哈希值时，则需要读取全部模型参数，因此我们不建议开发者继续使用这些格式的文件。

> - 在 .safetensors 中： 程序只需要读取文件开头的几 KB（即 Header 部分）。这一部分包含了所有需要的 Keys 和 Shape 信息。程序读完 Header 后立即停止，根本不需要去读取后面几个 GB 的具体参数数值。
> - 在 .pth / .bin (Pickle) 中： Pickle 是一种序列化格式，它类似于一段“程序代码”。要获取模型的结构（Keys 和 Shapes），通常必须按顺序解析（Unpickle）整个文件流。元数据和具体数值往往是交织在一起的，或者为了构建对象结构，必须先读取完整的数据。

因为开发者极大概率是要基于 Flux、Wan 等模型为 base model，然后调整模型架构的，所以我们需要计算我们的模型的 hash 值，最后写入到 ```Diffsynth.config.model_config``` 文件中

```python
tryon_series = [
    {
        "model_hash": "5e242df366a92fff7c66d820b45afade",
        "model_name": "wan_tryon_dit", # 我定义的新模型架构，基于Wan-2.2修改
        "model_class": "diffsynth.models.wan_tryon_dit.WanVTONDiT",
        "extra_kwargs": {   
            "patch_size": [1, 2, 2],
            "in_dim": 100,                   
            "dim": 3072,                 
            "ffn_dim": 14336,             
            "freq_dim": 256,
            "text_dim": 4096,
            "out_dim": 48,                  
            "num_heads": 24,                
            "num_layers": 30,          
            "eps": 1e-06,
        }
    },
]
```

### init

定义需要哪些组件（dit、text_encoder、vae），以及这些组件怎么处理数据（units），还有 model_fn 怎么计算

```python
    def __init__(self, device="cuda", torch_dtype=torch.bfloat16):
        super().__init__(
            device=device, 
            torch_dtype=torch_dtype,
            height_division_factor=16, 
            width_division_factor=16, 
            time_division_factor=4, 
            time_division_remainder=1
        )
        
        self.scheduler = FlowMatchScheduler("Wan")
        self.tokenizer = None
        self.text_encoder = None
        self.vae = None
        self.dit = None 
        self.siglip_model = None
        self.siglip_processor = None
        self.dino_model = None
        self.dino_processor = None
        self.in_iteration_models = ("dit",)

        # 3. 【关键】重写 Units 列表
        # 只保留 VTON 训练真正需要的
        self.units = [
            WanVideoUnit_ShapeChecker(),
            WanVideoUnit_NoiseInitializer(),
            WanVideoUnit_PromptEmbedder(),
            WanVideoUnit_InputVideoEmbedder(),
            WanVideoUnit_VTONInputs(),
            WanVideoUnit_UnifiedSequenceParallel(),
            WanVideoUnit_TeaCache(),
            WanVideoUnit_CfgMerger(),
        ]
        
        self.model_fn = model_fn_wan_vton
        
        self.post_units = []
```

### pretrain

前面所说，```model_pool.fetch_model```来加载在model_config.py中配置的模型，对于没有配置并且基类模型代码也没有在```diffsynth.models```中的，可以在```pretrain```中用 huggingface 加载

```python
    @staticmethod
    def from_pretrained(
        torch_dtype=torch.bfloat16,
        device="cuda",
        model_configs=[],
        tokenizer_config=None,
        siglip_path="/data2/qinzijing/models/google/siglip2-large-patch16-384", 
        dinov3_path="/data2/qinzijing/models/facebook/dinov3-vith16plus-pretrain-lvd1689m",
        **kwargs
    ):
        pipe = WanVTONPipeline(device=device, torch_dtype=torch_dtype)
        
        
        model_pool = pipe.download_and_load_models(model_configs)
        
        pipe.text_encoder = model_pool.fetch_model("wan_video_text_encoder")
        pipe.dit = model_pool.fetch_model("wan_tryon_dit") 
        pipe.vae = model_pool.fetch_model("wan_video_vae")
        
        pipe.siglip_processor = SiglipImageProcessor.from_pretrained(siglip_path)
        pipe.siglip_model = SiglipVisionModel.from_pretrained(siglip_path).to(dtype=torch_dtype).eval()

        pipe.dino_processor = AutoImageProcessor.from_pretrained(dinov3_path)
        pipe.dino_processor.crop_size = dict(height=384, width=384)
        pipe.dino_processor.size = dict(height=384, width=384)
        pipe.dino_model = AutoModel.from_pretrained(dinov3_path).to(dtype=torch_dtype).eval()

        if tokenizer_config:
            tokenizer_config.download_if_necessary()
            pipe.tokenizer = HuggingfaceTokenizer(name=tokenizer_config.path, seq_len=512, clean='whitespace')
            
        return pipe
```

### units
以下是按指定格式总结的所有的 `PipelineUnit`，要注意它的每一个 unit 的 input 和 output 的参数 key 名：
- WanVideoUnit_ShapeChecker
  - **Input 参数**: `height`, `width`, `num_frames`
  - **Output 参数**: `height`, `width`, `num_frames`
  - **作用**: 检查并调整输入视频的高度、宽度和帧数，确保它们符合模型的对齐要求（通常需要被特定的倍数整除）。
  - **需要模型**: 无
- WanVideoUnit_NoiseInitializer
  - **Input 参数**: `height`, `width`, `num_frames`, `seed`, `rand_device`, `vace_reference_image`
  - **Output 参数**: `noise`
  - **作用**: 根据输入维度和 VAE 的下采样因子计算 Latent 形状，并生成初始的高斯噪声。如果存在 VACE 参考图，会对噪声进行特定的拼接处理。
  - **需要模型**: 无（仅读取 `vae` 的配置参数）
- WanVideoUnit_InputVideoEmbedder
  - **Input 参数**: `input_video`, `noise`, `tiled`, `tile_size`, `tile_stride`, `vace_reference_image`
  - **Output 参数**: `latents`, `input_latents`
  - **作用**: 负责“视频生视频”或“图生视频”的输入处理。将输入视频预处理并使用 VAE 编码为 Latents。如果是推理模式，会根据 Scheduler 将 Latents 加噪作为起点；如果是训练模式，直接返回 Latents。
  - **需要模型**: `vae`
- WanVideoUnit_PromptEmbedder
  - **Input 参数**: Positive(`prompt`, `positive`), Negative(`negative_prompt`, `positive`)
  - **Output 参数**: `context`
  - **作用**: 处理文本提示词。使用 Tokenizer 将文本转为 ID，并使用文本编码器生成 Text Embeddings (`context`)，同时处理 Attention Mask 以对齐序列长度。
  - **需要模型**: `tokenizer`, `text_encoder`
- WanVideoUnit_ImageEmbedderCLIP
  - **Input 参数**: `input_image`, `end_image`, `height`, `width`
  - **Output 参数**: `clip_feature`
  - **作用**: 处理视觉条件（首帧和尾帧）。将图像 Resize 并预处理后，通过 CLIP Image Encoder 提取语义特征，用于 DiT 的交叉注意力机制。
  - **需要模型**: `image_encoder`
- WanVideoUnit_ImageEmbedderVAE
  - **Input 参数**: `input_image`, `end_image`, `num_frames`, `height`, `width`, `tiled`, `tile_size`, `tile_stride`
  - **Output 参数**: `y`
  - **作用**: 处理视觉条件（首帧和尾帧）的 Latent 表示。将图像扩展为视频张量（填充空帧），构造时序 Mask，并通过 VAE 编码。最终将 Mask 和编码后的 Latents 拼接作为条件 `y`。
  - **需要模型**: `vae`
- WanVideoUnit_ImageEmbedderFused
  - **Input 参数**: `input_image`, `latents`, `height`, `width`, `tiled`, `tile_size`, `tile_stride`
  - **Output 参数**: `latents`, `fuse_vae_embedding_in_latents`, `first_frame_latents`
  - **作用**: 专用于 `Wan2.2-TI2V-5B` 模型。将输入图像编码后，直接替换（融合）掉初始噪声 Latents 中的第一帧，作为生成过程的强约束起点。
  - **需要模型**: `vae`
- WanVideoUnit_FunControl
  - **Input 参数**: `control_video`, `num_frames`, `height`, `width`, `tiled`, `tile_size`, `tile_stride`, `clip_feature`, `y`, `latents`
  - **Output 参数**: `clip_feature`, `y`
  - **作用**: 处理 ControlNet 类的控制信号。将控制视频通过 VAE 编码，并拼接到现有的条件 `y` 中。如果 `clip_feature` 或 `y` 为空，会初始化零张量。
  - **需要模型**: `vae`
- WanVideoUnit_FunReference
  - **Input 参数**: `reference_image`, `height`, `width`
  - **Output 参数**: `reference_latents`, `clip_feature`
  - **作用**: 处理风格/主体参考图像。将参考图分别通过 VAE 编码为 Latents 和通过 CLIP 编码为特征，用于受控生成。
  - **需要模型**: `vae`, `image_encoder`
- WanVideoUnit_FunCameraControl
  - **Input 参数**: `height`, `width`, `num_frames`, `camera_control_direction`, `camera_control_speed`, `camera_control_origin`, `latents`, `input_image` 等
  - **Output 参数**: `control_camera_latents_input`, `y`
  - **作用**: 处理相机运镜控制。计算相机轨迹的 Plucker Embedding 并进行维度变换。同时处理首帧图像作为 VAE 编码的条件 `y`。
  - **需要模型**: `vae` (以及 DiT 内部的 `control_adapter`)
- WanVideoUnit_SpeedControl
  - **Input 参数**: `motion_bucket_id`
  - **Output 参数**: `motion_bucket_id`
  - **作用**: 将用于控制动作幅度的 `motion_bucket_id` 转换为模型可接受的 Tensor 格式。
  - **需要模型**: 无
- WanVideoUnit_VACE
  - **Input 参数**: `vace_video`, `vace_video_mask`, `vace_reference_image`, `vace_scale`, 等
  - **Output 参数**: `vace_context`, `vace_scale`
  - **作用**: 视频内容编辑（Video Active Content Editing）。根据 Mask 将视频分为前景和背景分别通过 VAE 编码，并结合参考图像的编码，拼接成 `vace_context` 用于编辑任务。
  - **需要模型**: `vae`
- WanVideoUnit_VAP
  - **Input 参数**: `vap_video`, `vap_prompt`, `negative_vap_prompt`, `end_image`, 等
  - **Output 参数**: `vap_clip_feature`, `vap_hidden_state`, `context_vap`
  - **作用**: 处理 Video-Audio-Prompt 任务。编码文本提示词、使用 CLIP 编码视频帧、使用 VAE 编码视频 Latents 和 Mask，生成多模态的条件输入。
  - **需要模型**: `text_encoder`, `vae`, `image_encoder`
- WanVideoUnit_UnifiedSequenceParallel
  - **Input 参数**: 无
  - **Output 参数**: `use_unified_sequence_parallel`
  - **作用**: 检查 Pipeline 是否开启了统一序列并行（Unified Sequence Parallel）功能，并返回标志位。
  - **需要模型**: 无
- WanVideoUnit_TeaCache
  - **Input 参数**: `num_inference_steps`, `tea_cache_l1_thresh`, `tea_cache_model_id`
  - **Output 参数**: `tea_cache`
  - **作用**: 初始化 TeaCache 对象。这是一种用于加速视频生成的缓存机制，利用时间步之间的相似性减少计算量。
  - **需要模型**: 无
- WanVideoUnit_CfgMerger
  - **Input 参数**: `inputs_shared`, `inputs_posi`, `inputs_nega`
  - **Output 参数**: 更新后的 `inputs_shared`
  - **作用**: 实现 Classifier-Free Guidance (CFG) 的数据准备。将正向条件（Positive）和负向条件（Negative）的 Tensor 在 Batch 维度上进行拼接（Concat），以便一次前向传播同时计算。
  - **需要模型**: 无
- WanVideoUnit_S2V
  - **Input 参数**: `input_audio`, `audio_embeds`, `s2v_pose_video`, `motion_video` 等
  - **Output 参数**: `audio_embeds`, `motion_latents`, `drop_motion_frames`, `s2v_pose_latents`
  - **作用**: 音频生视频（Sound-to-Video）的核心处理单元。使用 Audio Encoder 提取音频特征，使用 VAE 编码运动视频（Motion Video）和姿态视频（Pose Video）作为条件。
  - **需要模型**: `audio_encoder`, `vae`
- WanVideoPostUnit_S2V
  - **Input 参数**: `latents`, `motion_latents`, `drop_motion_frames`
  - **Output 参数**: `latents`
  - **作用**: S2V 任务的后处理。将运动控制的 Latents 拼接到生成的主 Latents 中（通常用于时序上的拼接或引导）。
  - **需要模型**: 无
- WanVideoUnit_AnimateVideoSplit
  - **Input 参数**: `input_video`, `animate_pose_video`, `animate_face_video`, `animate_inpaint_video`, `animate_mask_video`
  - **Output 参数**: 裁剪后的各类 `animate_` 视频
  - **作用**: 确保所有的控制视频（姿态、人脸、重绘、Mask）的长度与输入视频长度一致（通常裁剪掉多余的帧）。
  - **需要模型**: 无
- WanVideoUnit_AnimatePoseLatents
  - **Input 参数**: `animate_pose_video`, `tiled`, `tile_size`, `tile_stride`
  - **Output 参数**: `pose_latents`
  - **作用**: 将骨架/姿态控制视频通过 VAE 编码为 Latents，用于 Pose 驱动的生成。
  - **需要模型**: `vae`
- WanVideoUnit_AnimateFacePixelValues
  - **Input 参数**: `animate_face_video`
  - **Output 参数**: `face_pixel_values`
  - **作用**: 预处理人脸动画视频。正向条件为归一化的像素值，负向条件为全 -1 的 Tensor（表示空）。
  - **需要模型**: 无
- WanVideoUnit_AnimateInpaint
  - **Input 参数**: `animate_inpaint_video`, `animate_mask_video`, `input_image` 等
  - **Output 参数**: `y`
  - **作用**: 处理视频重绘（Inpainting）。编码背景视频、参考图像和重绘 Mask，构造包含空间和时间信息的条件张量 `y`。
  - **需要模型**: `vae`
- WanVideoUnit_LongCatVideo
  - **Input 参数**: `longcat_video`
  - **Output 参数**: `longcat_latents`
  - **作用**: 处理长视频输入。将长视频通过 VAE 编码为 Latents，可能用于长视频生成的上下文扩展或拼接任务。
  - **需要模型**: `vae`


但是我们往往需要自己定义自己的unit来处理数据，比如我需要用dinov3和siglip来提取特征：

```python
class WanVideoUnit_VTONInputs(PipelineUnit):
    def __init__(self):
        super().__init__(
            input_params=("cloth", "agnostic", "densepose", "mask", "tiled", "tile_size", "tile_stride", "height", "width"),
            output_params=("cloth_latents", "agnostic_latents", "densepose_latents", "mask_input", "ip_hidden_states"),
            onload_model_names=("vae")
        )

    def _prepare_vton_mask(self, mask_tensor, target_h, target_w):
        mask_padded = torch.cat(
            [
                torch.repeat_interleave(mask_tensor[:, :, 0:1], repeats=4, dim=2), 
                mask_tensor[:, :, 1:]
            ], dim=2
        )
        b, c, t, h, w = mask_padded.shape
        if t % 4 != 0:
            t_new = (t // 4) * 4
            mask_padded = mask_padded[:, :, :t_new, :, :]
            b, c, t, h, w = mask_padded.shape
        mask_view = mask_padded.view(b, c, t // 4, 4, h, w)
        mask_folded = mask_view.permute(0, 3, 1, 2, 4, 5).reshape(b, 4 * c, t // 4, h, w)
        mask_final = F.interpolate(
            mask_folded, 
            size=(mask_folded.shape[2], target_h, target_w), 
            mode="nearest" # Mask 建议用 nearest 保持二值边缘
        )        
        return mask_final

    def _get_visual_features(self, pipe, cloth_tensor):
        """
        完全复用 Reference Code 的逻辑进行特征提取
        """
        device = pipe.device
        dtype = pipe.torch_dtype
        
        # 将输入 tensor [-1, 1] 转换为 [0, 1]
        image_01 = cloth_tensor * 0.5 + 0.5

        # --- 内部辅助函数: 对应 encode_image_emb 中的 process_with_processor ---
        def process_with_processor(images, processor):
            # images: (B, C, H, W) range [0, 1]
            if isinstance(images, torch.Tensor):
                # Processor 通常期望 float32 输入进行归一化
                images = images.to(torch.float32)
            
            return processor(
                images=images,
                return_tensors="pt",
                do_resize=False,       # 我们自己做 resize (interpolate)
                do_rescale=False,      # 输入已经是 [0,1]，不需要 /255
                do_normalize=True,     # 只做 ImageNet Normalize
                data_format="channels_first", 
                input_data_format="channels_first"
            ).pixel_values.to(device=device, dtype=dtype)

        # --- 内部辅助函数: SigLIP 特征提取 ---
        def encode_siglip(pixel_values):
            # 将模型临时移到 device (如果之前在 CPU)
            pipe.siglip_model.to(device)
            with torch.no_grad():
                res = pipe.siglip_model(pixel_values, output_hidden_states=True)
                
                # Deep features: last_hidden_state
                embeds = res.last_hidden_state
                
                # Shallow features: layers [5, 11, 23]
                # SigLIP hidden_states 包含 embedding layer 输出，所以 index 要注意
                # Reference code 用的是 [5, 11, 23]，我们直接照搬
                shallow = torch.cat([res.hidden_states[i] for i in [5, 11, 23]], dim=1)
            return embeds, shallow

        # --- 内部辅助函数: DINOv3 特征提取 ---
        def encode_dino(pixel_values):
            pipe.dino_model.to(device)
            with torch.no_grad():
                res = pipe.dino_model(pixel_values, output_hidden_states=True)
                
                # DINOv3 通常有 register tokens 或 class token，Reference code 做了切片 [:, 5:]
                embeds = res.last_hidden_state[:, 5:]
                
                # Shallow features: layers [7, 15, 31], 切片 [:, 5:]
                shallow = torch.cat([res.hidden_states[i][:, 5:] for i in [7, 15, 31]], dim=1)
            return embeds, shallow

        # === Step B: Low Res (384x384) ===
        image_low_res = F.interpolate(image_01, size=(384, 384), mode='bicubic', align_corners=False, antialias=True)
        
        siglip_low_input = process_with_processor(image_low_res, pipe.siglip_processor)
        dino_low_input = process_with_processor(image_low_res, pipe.dino_processor)
        
        siglip_embeds_low, siglip_shallow_low = encode_siglip(siglip_low_input)
        dinov3_embeds_low, dinov3_shallow_low = encode_dino(dino_low_input)
        
        image_embeds_low_res_deep = torch.cat([siglip_embeds_low, dinov3_embeds_low], dim=2)
        image_embeds_low_res_shallow = torch.cat([siglip_shallow_low, dinov3_shallow_low], dim=2)

        # === Step C: High Res (768x768) & Crop ===
        image_high_res = F.interpolate(image_01, size=(768, 768), mode='bicubic', align_corners=False, antialias=True)
        
        # 切分成 4 个 384x384
        crops = [
            image_high_res[:, :, 0:384, 0:384],      # Top-Left
            image_high_res[:, :, 0:384, 384:768],    # Top-Right
            image_high_res[:, :, 384:768, 0:384],    # Bottom-Left
            image_high_res[:, :, 384:768, 384:768],  # Bottom-Right
        ]
        image_crops = torch.stack(crops, dim=1) # (B, 4, C, H, W)
        b, n, c, h, w = image_crops.shape
        image_crops_flat = rearrange(image_crops, 'b n c h w -> (b n) c h w')
        
        # === Step E: High Res Features ===
        siglip_input_high = process_with_processor(image_crops_flat, pipe.siglip_processor)
        dino_input_high = process_with_processor(image_crops_flat, pipe.dino_processor)
        
        siglip_embeds_high, _ = encode_siglip(siglip_input_high)
        dinov3_embeds_high, _ = encode_dino(dino_input_high)
        
        # Reshape back: (B*4, L, D) -> (B, 4*L, D)
        siglip_high_res_deep = rearrange(siglip_embeds_high, '(b n) l d -> b (n l) d', n=n)
        dinov3_high_res_deep = rearrange(dinov3_embeds_high, '(b n) l d -> b (n l) d', n=n)
        
        image_embeds_high_res_deep = torch.cat([siglip_high_res_deep, dinov3_high_res_deep], dim=2)

        return {
            "image_embeds_low_res_shallow": image_embeds_low_res_shallow,
            "image_embeds_low_res_deep": image_embeds_low_res_deep,
            "image_embeds_high_res_deep": image_embeds_high_res_deep
        }

    def process(self, pipe, cloth, agnostic, densepose, mask, tiled, tile_size, tile_stride, height, width):
        if any(x is None for x in [cloth, agnostic, densepose, mask]):
            return {}

        pipe.load_models_to_device(self.onload_model_names)

        def encode_condition(image_list_or_tensor):
            video_tensor = pipe.preprocess_video(image_list_or_tensor) # B C T H W
            latents = pipe.vae.encode(
                video_tensor, 
                device=pipe.device, 
                tiled=tiled, 
                tile_size=tile_size, 
                tile_stride=tile_stride
            )
            return latents.to(dtype=pipe.torch_dtype, device=pipe.device)

        cloth_latents = encode_condition(cloth)
        agnostic_latents = encode_condition(agnostic)
        densepose_latents = encode_condition(densepose)

        mask_tensor = pipe.preprocess_video(mask, min_value=0, max_value=1).to(device=pipe.device, dtype=pipe.torch_dtype)
        if mask_tensor.shape[1] == 3:
            mask_tensor = mask_tensor[:, 0:1, :, :, :]
        scale_factor = pipe.vae.upsampling_factor if hasattr(pipe.vae, 'upsampling_factor') else 8
        mask_input = self._prepare_vton_mask(mask_tensor, height // scale_factor, width // scale_factor)

        cloth_tensor = pipe.preprocess_video(cloth, min_value=-1, max_value=1)
        cloth_tensor = cloth_tensor[:, :, 0, :, :] 
        ip_hidden_states = self._get_visual_features(pipe, cloth_tensor)

        return {
            "cloth_latents": cloth_latents,
            "agnostic_latents": agnostic_latents,
            "densepose_latents": densepose_latents,
            "mask_input": mask_input,
            "ip_hidden_states": ip_hidden_states    
        }
```

### call

```call``` 主要是推理时使用，传入参数，最后输出 video （可以调整输出 latent 或者直接的mp4）。可以重点关注它的 input 的 key 名， 与 unit 是相匹配的。

```python
@torch.no_grad()
def __call__(
    self,
    cloth: Image.Image,                  
    agnostic: List[Image.Image],         
    densepose: List[Image.Image],         
    mask: List[Image.Image],    
    
    prompt: str,
    negative_prompt: Optional[str] = "",
    
    input_video: Optional[List[Image.Image]] = None,          

    height: int = 480,
    width: int = 832,
    num_frames: int = 16, # 如果是单图生成，设为 1

    seed: Optional[int] = None,
    cfg_scale: float = 5.0,
    cfg_merge: Optional[bool] = False,
    num_inference_steps: int = 50,
    denoising_strength: float = 1.0, # 1.0 = 全量生成, <1.0 = 图生图/视频生视频
    sigma_shift: float = 5.0,
    tiled: bool = True,
    tile_size: Tuple[int, int] = (30, 52),
    tile_stride: Tuple[int, int] = (15, 26),
    tea_cache_l1_thresh: Optional[float] = None,
    progress_bar_cmd=tqdm,
    output_type: Literal["quantized", "floatpoint"] = "quantized", 
):
    self.scheduler.set_timesteps(num_inference_steps, denoising_strength=denoising_strength, shift=sigma_shift)
    inputs_posi = {
        "prompt": prompt,
        "tea_cache_l1_thresh": tea_cache_l1_thresh, 
        "num_inference_steps": num_inference_steps,
    }
    
    inputs_nega = {
        "negative_prompt": negative_prompt,
        "tea_cache_l1_thresh": tea_cache_l1_thresh, 
        "num_inference_steps": num_inference_steps,
    }
    
    inputs_shared = {
        "cloth": cloth,
        "agnostic": agnostic,
        "densepose": densepose,
        "mask": mask,
        
        "height": height, 
        "width": width, 
        "num_frames": num_frames,
        "seed": seed, 
        "rand_device": self.device, 

        "cfg_scale": cfg_scale,
        "cfg_merge": cfg_merge, 
        "denoising_strength": denoising_strength,
        "sigma_shift": sigma_shift,

        "tiled": tiled, 
        "tile_size": tile_size, 
        "tile_stride": tile_stride,
        "input_video": input_video, 
    }
    for unit in self.units:
        inputs_shared, inputs_posi, inputs_nega = self.unit_runner(
            unit, self, inputs_shared, inputs_posi, inputs_nega
        )
    self.load_models_to_device(self.in_iteration_models)
    models = {name: getattr(self, name) for name in self.in_iteration_models}
    
    for progress_id, timestep in enumerate(progress_bar_cmd(self.scheduler.timesteps)):
        timestep = timestep.unsqueeze(0).to(dtype=self.torch_dtype, device=self.device)
        
        noise_pred_posi = self.model_fn(
            **models, 
            **inputs_shared, 
            **inputs_posi, 
            timestep=timestep
        )
        
        noise_pred_posi = self.model_fn(**models, **inputs_shared, **inputs_posi, timestep=timestep)
        if cfg_scale != 1.0:
            if cfg_merge:
                noise_pred_posi, noise_pred_nega = noise_pred_posi.chunk(2, dim=0)
            else:
                noise_pred_nega = self.model_fn(**models, **inputs_shared, **inputs_nega, timestep=timestep)
            noise_pred = noise_pred_nega + cfg_scale * (noise_pred_posi - noise_pred_nega)
        else:
            noise_pred = noise_pred_posi

        inputs_shared["latents"] = self.scheduler.step(
            noise_pred, 
            self.scheduler.timesteps[progress_id], 
            inputs_shared["latents"]
        )
        
    for unit in self.post_units:
        inputs_shared, _, _ = self.unit_runner(unit, self, inputs_shared, inputs_posi, inputs_nega)
        
    self.load_models_to_device(['vae'])
    video = self.vae.decode(inputs_shared["latents"], device=self.device, tiled=tiled, tile_size=tile_size, tile_stride=tile_stride)
    if output_type == "quantized":
        video = self.vae_output_to_video(video)
    elif output_type == "floatpoint":
        pass
    self.load_models_to_device([])
    return video

```

### training module

上面我已经把具体的训推 pipeline 构造完毕，剩下的就是我们的训练模型的代码的编写。训练模块在 Pipeline 上层进行封装，继承 diffsynth.diffusion.training_module 中的 DiffusionTrainingModule，我们需为训练模块提供必要的 __init__ 和 forward 方法。

#### init

在 ```__init__``` 中需进行模型的初始化，先加载模型，然后将其切换到训练模式。
一般情况下使用 switch_pipe_to_training_mode 切换训练模式，并且可以选择训练的模块，```trainable_models```选择训练的模块，比如 dit、vae、text_encoder 等。 ```lora_base_model``` 选择 lora 挂载在哪几个模块。
 
```python
self.switch_pipe_to_training_mode(
    self.pipe,
    trainable_models=None, 
    lora_base_model="dit",
    lora_target_modules=lora_target_str,
    lora_rank=self.args.lora_rank, 
)
```


#### forward 

```forward``` 可以计算 loss，与 pipeline 的 call 函数类似。

```python
def forward(self, data):
    inputs_posi = {"prompt": data["prompt"]} 
    inputs_nega = {"negative_prompt": ""}
    
    inputs_shared = {
        "input_video": data["input"], 
        "cloth": data["cloth"],
        "agnostic": data["agnostic"],
        "densepose": data["densepose"],
        "mask": data["mask"],
        "height": data["input"][0].size[1], 
        "width": data["input"][0].size[0],  
        "num_frames": len(data["input"]),
        "cfg_scale": 1.0,
        "cfg_merge": False, 
        "tiled": True,
        "tile_size": (30, 52),   
        "tile_stride": (15, 26), 
        "rand_device": self.pipe.device,
        "use_gradient_checkpointing": self.use_gradient_checkpointing,
    }

    for unit in self.pipe.units:
        inputs_shared, inputs_posi, inputs_nega = self.pipe.unit_runner(
            unit, self.pipe, inputs_shared, inputs_posi, inputs_nega
        )
        
    loss = FlowMatchSFTLoss(self.pipe, **inputs_shared, **inputs_posi)
    
    return loss

```



## models

魔改模型基本都是继承 WanModel , 然后修改它的 ditblock 部分，ditblock 部分又可以使用继承 crossattention 的自定义 attention module，通过在这三个 module 可以自由处理组合传入的各种 condition 信息。

```python
class WanVTONDiTBlock(DiTBlock):
    def __init__(self, dim: int, num_heads: int, ffn_dim: int, eps: float = 1e-6):
        super().__init__(has_image_input=False, dim=dim, num_heads=num_heads, ffn_dim=ffn_dim, eps=eps)
        self.cross_attn = WanVTONCrossAttention(dim, num_heads, eps)
```

```python 
class WanVTONDiT(WanModel):
    def __init__
```

```python 
class WanVTONCrossAttention(CrossAttention):
    def __init__(self, dim: int, num_heads: int, eps: float = 1e-6):
        super().__init__(dim, num_heads, eps, has_image_input=False)
```

## 其他部分

上面介绍了主要的训练流程需要准备和注意的细节，包括 数据处理、训推 pipeline、模型修改，这一部分主要介绍 Diffsynth 的一些其他细节

### 训练部分加载