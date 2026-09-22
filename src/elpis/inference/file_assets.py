"""Read-only range assets extending HACF FMS ABI v2.

Buffered pread mode: native FMS RAM is bounded, Linux page cache is NOT charged
or bounded by this extension. Physical bytes mean bytes returned by pread,
not device-level I/O (which cannot be inferred from buffered reads).
Every page is verified before native registration or exposure to inference.
"""
from collections import OrderedDict
from contextlib import contextmanager
import ctypes as C
from dataclasses import dataclass
import os
from pathlib import Path
import stat
from threading import RLock
from time import perf_counter_ns
from .contracts import Code, InferenceError, digest_value, identity, integer, require


def raw_digest(data):
    """Canonical byte-content identity; no direct digest sink."""
    require(
        isinstance(data, (bytes, bytearray, memoryview)),
        detail='raw byte content',
    )
    return identity('raw-bytes', bytes(data))


def bounded_path(root, path):
    root, path = Path(root), Path(path)
    require(root.is_absolute() and '..' not in root.parts, detail='workspace root')
    path = path if path.is_absolute() else root / path
    require('..' not in path.parts and path.is_relative_to(root), Code.INVALID, 'path boundary')
    # Refuse symlinks without resolving their targets or traversing outside root.
    current = root
    require(not current.is_symlink(), detail='root symlink')
    for part in path.relative_to(root).parts:
        current = current / part
        require(not current.is_symlink(), detail='symlink forbidden')
    return path


@dataclass(frozen=True)
class AssetManifest:
    size: int
    page_size: int
    content: str
    pages: tuple[str, ...]
    schema: str = 'elpis.fms.file-asset.r0'

    def __post_init__(self):
        require(self.schema == 'elpis.fms.file-asset.r0')
        integer(self.size, 1)
        integer(self.page_size, 1, 16 * 1024 * 1024)
        digest_value(self.content)
        require(type(self.pages) is tuple and len(self.pages) == (self.size + self.page_size-1)//self.page_size,
                detail='page map geometry')
        for digest in self.pages:
            digest_value(digest)

    @property
    def digest(self):
        return identity('file-asset.manifest', self)


def inspect_asset(root, path, page_size):
    """Offline intake: streaming page identities, never full buffering."""
    path = bounded_path(root, path)
    integer(page_size, 1, 16 * 1024 * 1024)
    pages, size = [], 0
    try:
        with path.open('rb') as f:
            before = os.fstat(f.fileno())
            require(stat.S_ISREG(before.st_mode), detail='regular asset required')
            while data := f.read(page_size):
                pages.append(raw_digest(data))
                size += len(data)
            after = os.fstat(f.fileno())
            require(_stamp(before) == _stamp(after), Code.INTEGRITY, 'asset changed during intake')
    except OSError as exc:
        raise InferenceError(Code.IO, 'asset intake') from exc
    pages = tuple(pages)
    content = identity(
        'file-asset.content-map',
        dict(size=size, page_size=page_size, pages=pages),
    )
    return AssetManifest(size, page_size, content, pages)


def _stamp(s):
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


class _NativePages:
    def __init__(self, library, scratch, warm_bytes, max_pages, absent_policy):
        self.lib = C.CDLL(str(library))
        lib = self.lib
        vp, u64 = C.c_void_p, C.c_uint64
        signatures = {
            'elpis_fms_file_create': ([C.c_char_p,u64,C.c_uint32,C.c_int,C.POINTER(vp)],C.c_int),
            'fms_register': ([vp,C.c_uint32,u64,C.c_int,C.c_float,vp,C.POINTER(u64)],C.c_int),
            'fms_unregister': ([vp,u64],C.c_int),
            'fms_lease_acquire': ([vp,u64,C.c_int,C.c_uint,C.POINTER(vp)],C.c_int),
            'fms_lease_ptr': ([vp],vp), 'fms_lease_tier': ([vp],C.c_int),
            'fms_lease_release': ([vp,vp],C.c_int),
            'elpis_fms_file_stats': ([vp,C.POINTER(u64)],C.c_int),
            'fms_destroy': ([vp],None),
        }
        for name,(args,result) in signatures.items():
            f=getattr(lib,name); f.argtypes=args; f.restype=result
        self.ctx=vp()
        self.check(lib.elpis_fms_file_create(os.fsencode(scratch),warm_bytes,max_pages,absent_policy,C.byref(self.ctx)))

    @staticmethod
    def check(rc):
        if rc < 0:
            code={-2:Code.LIMIT,-3:Code.MISSING,-4:Code.BUSY,-5:Code.UNSUPPORTED,
                  -6:Code.IO,-7:Code.LIMIT,-9:Code.INTEGRITY,-10:Code.DEVICE}.get(rc,Code.INVALID)
            raise InferenceError(code,f'native FMS status {rc}')
        return rc

    def register(self,data):
        oid=C.c_uint64()
        buffer=C.create_string_buffer(data)
        self.check(self.lib.fms_register(self.ctx,0x50414745,len(data),1,0,buffer,C.byref(oid)))
        return oid.value

    def acquire(self,oid,tier):
        lease=C.c_void_p()
        self.check(self.lib.fms_lease_acquire(self.ctx,oid,tier,1,C.byref(lease)))
        return lease,self.lib.fms_lease_ptr(lease),self.lib.fms_lease_tier(lease)

    def release(self,lease):
        self.check(self.lib.fms_lease_release(self.ctx,lease))

    def evict(self,oid):
        self.check(self.lib.fms_unregister(self.ctx,oid))

    def stats(self):
        values=(C.c_uint64*8)()
        self.check(self.lib.elpis_fms_file_stats(self.ctx,values))
        return dict(zip(('hot','warm','native_cold','ram','device','native_storage','pages','pinned'),values))

    def close(self):
        self.lib.fms_destroy(self.ctx)


class RangeLease:
    def __init__(self,owner,parts,offset,length,actual_tier):
        self._owner=owner; self._parts=parts
        self.offset=offset; self.length=length; self.actual_tier=actual_tier
        self._active=True

    def read(self):
        with self._owner._lock:
            require(self._active,Code.CLOSED,'released range lease')
            return b''.join(C.string_at(ptr+start,size) for _,_,ptr,start,size in self._parts)

    def bind_fence(self,fence):
        # CPU POSIX PAL has no device/fence facility. Never pretend completion.
        raise InferenceError(Code.UNSUPPORTED,'CPU file-asset provider has no accelerator fences')

    def release(self):
        with self._owner._lock:
            require(self._active,Code.CLOSED,'double range release')
            for key,lease,_,_,_ in self._parts:
                self._owner._native.release(lease)
                self._owner._pins[key]-=1
            self._active=False

    def __enter__(self): return self
    def __exit__(self,*exc): self.release()


class FMSFileAssets:
    """Additive external COLD catalog + bounded native FMS page materialization.

    No writable replicas. Registration is metadata-only. Eviction unregisters
    verified native pages; externally owned immutable storage is never deleted.
    A serialized I/O critical section prioritizes clear accounting in R0.
    """
    def __init__(self,*,root,library,scratch,warm_bytes=65536,staging_bytes=65536,
                 storage_bytes=1<<40,max_pages=1024,hot_absent_policy='FOLD_DOWN'):
        self.root=Path(root)
        library=bounded_path(root,library); scratch=bounded_path(root,scratch)
        integer(warm_bytes,1); integer(staging_bytes,1); integer(storage_bytes,1); integer(max_pages,1,(1<<32)-1)
        require(hot_absent_policy in ('FOLD_DOWN','REJECT'))
        scratch.mkdir(parents=True,exist_ok=True)
        self._native=_NativePages(library,scratch,warm_bytes,max_pages,int(hot_absent_policy=='REJECT'))
        self.warm_budget=warm_bytes; self.staging_budget=staging_bytes; self.storage_budget=storage_bytes
        self._lock=RLock(); self._assets={}; self._pages=OrderedDict(); self._pins={}; self._closed=False
        self.telemetry={'semantic_bytes':0,'pread_bytes':0,'reads':0,'hits':0,'misses':0,
                        'read_ns':0,'integrity_ns':0,'staging_ns':0,'staging_high_water':0}

    def _open(self): require(not self._closed,Code.CLOSED,'FMS file provider')

    def register(self,path,manifest,*,expected_manifest):
        with self._lock:
            self._open()
            require(type(manifest) is AssetManifest and manifest.digest==expected_manifest,Code.IDENTITY,'page-map root')
            require(manifest.page_size <= min(self.staging_budget//4,self.warm_budget),Code.LIMIT,'page staging (four-copy upper bound)')
            if manifest.digest in self._assets: return manifest.digest
            require(sum(v[1].size for v in self._assets.values())+manifest.size<=self.storage_budget,Code.LIMIT,'external COLD budget')
            path=bounded_path(self.root,path)
            try:
                fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
            except FileNotFoundError as exc:
                raise InferenceError(Code.MISSING,'backing asset') from exc
            except OSError as exc:
                raise InferenceError(Code.IO,'open asset') from exc
            try:
                s=os.fstat(fd)
                require(stat.S_ISREG(s.st_mode) and s.st_size==manifest.size,Code.INTEGRITY,'asset geometry')
            except BaseException:
                os.close(fd)
                raise
            self._assets[manifest.digest]=(fd,manifest,_stamp(s))
            return manifest.digest

    def _load(self,asset,page):
        fd,m,stamp=self._assets[asset]
        require(_stamp(os.fstat(fd))==stamp,Code.INTEGRITY,'changed backing file')
        key=(asset,page)
        if key in self._pages:
            self.telemetry['hits']+=1
            self._pages.move_to_end(key)
            return self._pages[key]
        self.telemetry['misses']+=1
        start=page*m.page_size; count=min(m.page_size,m.size-start)
        data=bytearray()
        begin=perf_counter_ns()
        try:
            while len(data)<count:
                try: piece=os.pread(fd,count-len(data),start+len(data))
                except InterruptedError: continue
                require(bool(piece),Code.IO,'short backing read')
                self.telemetry['pread_bytes']+=len(piece)
                self.telemetry['reads']+=1
                data.extend(piece)
        except OSError as exc:
            raise InferenceError(Code.IO,'pread') from exc
        self.telemetry['read_ns']+=perf_counter_ns()-begin
        begin=perf_counter_ns()
        require(raw_digest(data)==m.pages[page],Code.INTEGRITY,'backing page digest')
        require(_stamp(os.fstat(fd))==stamp,Code.INTEGRITY,'asset changed during read')
        self.telemetry['integrity_ns']+=perf_counter_ns()-begin
        self.telemetry['staging_high_water']=max(self.telemetry['staging_high_water'],4*count)
        begin=perf_counter_ns()
        while True:
            try:
                oid=self._native.register(bytes(data))
                break
            except InferenceError as exc:
                if exc.code not in (Code.LIMIT,Code.UNSUPPORTED): raise
                victim=next((k for k in self._pages if self._pins[k]==0),None)
                require(victim is not None,Code.LIMIT,'all native pages leased or budget too small')
                self._native.evict(self._pages.pop(victim))
                del self._pins[victim]
        self.telemetry['staging_ns']+=perf_counter_ns()-begin
        self._pages[key]=oid; self._pins[key]=0
        return oid

    def acquire(self,asset,offset,length,*,tier='WARM'):
        with self._lock:
            self._open()
            require(asset in self._assets,Code.MISSING,'asset')
            integer(offset); integer(length,1)
            require(tier in ('HOT','WARM'),Code.UNSUPPORTED,'COLD is external storage, not an addressable lease')
            m=self._assets[asset][1]
            require(offset+length<=m.size,detail='range outside asset')
            first,last=offset//m.page_size,(offset+length-1)//m.page_size
            require((last-first+1)*m.page_size<=self.warm_budget,Code.LIMIT,'range exceeds native budget')
            self.telemetry['semantic_bytes']+=length
            parts=[]; actual=1
            try:
                for page in range(first,last+1):
                    key=(asset,page); oid=self._load(asset,page)
                    lease,ptr,actual=self._native.acquire(oid,0 if tier=='HOT' else 1)
                    self._pins[key]+=1
                    start=max(offset,page*m.page_size)-page*m.page_size
                    end=min(offset+length,(page+1)*m.page_size)-page*m.page_size
                    parts.append((key,lease,ptr,start,end-start))
            except BaseException:
                for key,lease,_,_,_ in parts:
                    self._native.release(lease); self._pins[key]-=1
                raise
            require(actual in (0,1),Code.INTEGRITY,'native lease tier')
            return RangeLease(self,parts,offset,length,('HOT','WARM')[actual])

    def evict(self,asset=None):
        with self._lock:
            self._open()
            keys=[key for key in self._pages if asset is None or key[0]==asset]
            require(not any(self._pins[key] for key in keys),Code.BUSY,'active range lease')
            for key in keys:
                self._native.evict(self._pages.pop(key)); del self._pins[key]

    def stats(self):
        with self._lock:
            self._open()
            return dict(self._native.stats(),external_cold=sum(v[1].size for v in self._assets.values()),
                        buffered_page_cache_accounted=False,**self.telemetry)

    def close(self):
        with self._lock:
            self._open()
            self.evict()
            for fd,_,_ in self._assets.values(): os.close(fd)
            self._assets.clear(); self._native.close(); self._closed=True

    def __enter__(self): return self
    def __exit__(self,*exc): self.close()
