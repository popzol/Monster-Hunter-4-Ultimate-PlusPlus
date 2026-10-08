"""Game audio: MADP (.mca) tracks with DSP ADPCM decoding and encoding (the encoder needs numpy),
and STRQ (.stq) stream queues."""

from .madp import (Channel, DspState, Madp, SeekPoint, build_madp, decode_madp, encode_madp, parse_madp,
                   prepare_pcm)
from .strq import (build_strq, parse_strq, queue_archives, queue_files, queue_name, read_queue, replace_queue,
                   romfs_path, stream_entry, stream_path, unused_streams)
from .wav import read_wav, write_wav

__all__ = ["Channel", "DspState", "Madp", "SeekPoint", "build_madp", "build_strq", "decode_madp", "encode_madp",
           "parse_madp", "parse_strq", "prepare_pcm", "queue_archives", "queue_files", "queue_name", "read_queue",
           "read_wav", "replace_queue", "romfs_path", "stream_entry", "stream_path", "unused_streams", "write_wav"]
