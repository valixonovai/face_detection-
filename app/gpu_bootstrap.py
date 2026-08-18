"""
Windows'da onnxruntime-gpu CUDA/cuDNN DLL'larini topishi uchun.
`pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cudnn-cu12
nvidia-cufft-cu12` orqali o'rnatilgan DLL'lar tizim PATH'ida emas — ular shu
paketlarning `bin/` papkalarida turadi. onnxruntime import qilinishidan oldin
shu papkalarni DLL qidiruv yo'liga qo'shib qo'yamiz (to'liq CUDA Toolkit
o'rnatmasdan GPU ishlatish uchun).
"""
import importlib
import os
import sys


def register_nvidia_dll_dirs() -> None:
    if sys.platform != "win32":
        return

    for module_name in (
        "nvidia.cuda_runtime",
        "nvidia.cublas",
        "nvidia.cudnn",
        "nvidia.cufft",
        "nvidia.curand",
        "nvidia.cusparse",
        "nvidia.cusolver",
        "nvidia.cuda_nvrtc",
        "nvidia.nvjitlink",
    ):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for path in module.__path__:
            bin_dir = os.path.join(path, "bin")
            if os.path.isdir(bin_dir):
                os.add_dll_directory(bin_dir)
                # onnxruntime o'zining provider DLL'larini classic LoadLibrary orqali
                # yuklaydi, bu add_dll_directory'ni emas, PATH'ni ko'radi.
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


register_nvidia_dll_dirs()
