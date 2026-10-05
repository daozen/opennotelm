# 031 · Deck PDF 无损体积优化

日期：2026-10-04。基于419fae8。用户要求减小约20页/70MB的下载文件，同时不损失画质。

## 契约

新生成的整页/原生兼容 PDF 使用无损图片压缩，保留原像素、颜色样本、分辨率、页面尺寸、
书签和原生文字层。不降低尺寸、不减少颜色、不使用 JPEG 有损重编码、不调用模型。
图片复杂度不同，缩小比例不同；不承诺所有 Deck 达到同一体积。

已保存 PDF 不因升级或普通下载被改写。用户在“更多操作”选择“重新生成 PDF 文件”，
从既有页图生成新的压缩版文件，成功后单份/批量下载优先使用该版；旧文件及其原链接仍有效，
但两版都受原有页面修订/过期检查。压缩失败时原文件继续可下载，不清理原文件。
重新规划/生图不是 PDF 优化的前提；同一压缩版本成功后重复导出复用缓存。

## 实现

ReportLab 原路径对展开的RGB样本直接Flate压缩，再套ASCII85，未利用相邻像素预测，
导致典型照片/插画页面体积明显大于PNG。`pdf_images.py`处理应用自身Canvas生成的有界
8-bit DeviceRGB/DeviceGray图片流，去掉ASCII85，在zlib级别9原样本压缩与PNG过滤后IDAT
之间选择更小者。预测版使用PDF FlateDecode的Predictor15/Columns/Colors/BitsPerComponent。
不可压缩噪声可以选择原样本，不为预测字典增大图片流。颜色/透明度行为保持原Canvas契约，
不新增透明度解释、ICC变换或文字层。未支持的图片流保持原状。

整页`write_page`的单页PDF与最终`assemble_pdf`共用此边界；新整页单页PDF标记编码版本，
最终组装直接复用，避免两次编码；旧单页与原生兼容仍从既有PNG无损导出。
PNG预览/缩略图/资产原字节不变。
pypdf已编码流的内部数据写入封装在一处，锁定依赖及像素/独立渲染测试验证兼容。

旧`EXPORT_VERSION=image-aligned-text-v2`和`snapshot()`原签名算法保持不变。
压缩版额外签名为SHA256(`lossless-predictor-v1:旧签名`)，单独pdf_exports行/目录，
不迁移数据库。当前文件优先选择压缩版ready，其次旧版ready，最后非ready状态；
按旧/新签名校验下载、修订仍让两者过期。新增encoding不更改Deck/页图内容签名。
导出队列payload仅在显式export加入optimize标记；普通恢复优先复用已完成旧版。
压缩线程沿用取消shield/join、revision guard与原子发布，批量ZIP保留所选PDF字节。

验证和部署范围见[ACCEPTANCE](../ACCEPTANCE.md)。
