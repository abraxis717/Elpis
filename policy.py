"""Offline successor authority validator. This is not a runtime service."""
import hashlib,json,pathlib,re,sys,tomllib
if sys.flags.optimize: raise RuntimeError('optimized Python forbidden for authority validation')
PARENT_MANIFEST='53cf494b069dd48e2c2ae0a8bac447b8499e34340557089423c75d44ef31391e'
HISTORY_SHA='4ebd46c2cc2d3727186adf51b0d68f6f27e2f1864a56bdc92e3b9d771b683a41'
AMENDMENT_SHA='e6120a782d0a713f287933f9bac02a3d2b36d4fa2ff21f33c6a7cbfd07c7ceb6'
BUILD_SHA='b12c55860ab938aaedb8206f153e72ad8e6df7b4ba4e54a0e4649de6ff31f4ce'
WRAPPER_SHA='766004ae7719c90310d07414e668cef53c6519df7b08e77adb3336d19424a111'
BASE='f8f53a55cc935c9a61e902fc7e2c5130ca9b68a0'
PARENT_RESULT='128ebba2be5b169db171517a5208a623ecf01c00de08a283bb88191b03ad2a27'
ROLES=['ELPIS LLM COMPUTES AND COMMUNICATES','GEODOME ORGANIZES AND TRANSPORTS','CGC ADAPTS AND LEARNS','ECS_C REMEMBERS AND BINDS EVIDENCE AUTHORITY','RUNTIMECORE GOVERNS EXECUTION','FMS MATERIALIZES RESOURCES']
INVARIANTS={'mutable_operational_state':'VOLATILE_ONLY','autonomous_storage_writes':False,'swap_spill':False,'persistent_journal':False,'implicit_checkpoint':False,'disk_weight_mutation':False,'unbounded_growth':False,'session_genesis':'FRESH','model_commit_authority':False,'network_process_creation':False,'shared_writable_mappings':False,'offline_development_separate':True}
LIMITS={'cells':1024,'evidence_records':1024,'evidence_links':4096,'host_session_entity_capacity':16,'host_ticks':65536,'model_attempts':4096,'operator_commands':4096,'pending_proposals':1,'queued_replies_per_lane':1,'max_payload_bytes':2308,'max_packet_bytes':2312,'poll_max_ms':100}
CLAIMS={'native_core':'PASS_CR7_P3A','warm_ram_residency':'PASS_NONMOVING','independent_mock_execution':'PASS_MOCK_ONLY','runtime_model_loss':'PASS_OBSERVED_PROCESS_LOSS','actual_neural_inference':'NOT_TESTED','neural_augmentation_utility':'NOT_TESTED','geometry_advantage':'NOT_ESTABLISHED','collective_learning':'NOT_TESTED','fms_generic_allocator':'NOT_IMPLEMENTED','fms_immutable_assets':'NOT_TESTED','production_enrollment':'NOT_IMPLEMENTED','model_authentication':'TRUSTED_SUPERVISOR_CAPABILITIES_ONLY','host_reconnect':'NOT_IMPLEMENTED','deployment':'NOT_AUTHORIZED'}
ARCHIVES={'libcr5_production.a':'1ce3589231d06cc3c3dd7ce094d98049e87a458e3aa17195317b73eee7ab6498','libcr6_protocol.a':'24b2f1bbe9a290b9d43ae3cb45bb3f04ec88c90571ae5eb6f8ce52beac642265','libcr6_ipc.a':'43ce26e1d07a60f709eef4d43672fb33ceb456dc1f730197c9935ff7ffa05695','libcr6_ipc_guard.a':'76bf8d44370a220140574f0d5f01669779d3bcb21804fe9b9c8a07dffdc1c054'}
REMOVED={'native/runtime/src/'+n+'.rs' for n in ('ffi','fuel','substrate')}
META={'ELPIS_SYSTEM.json','README.md','docs/ELPIS_MISSION.md','docs/AMENDMENT_4.md','source.sha256','build_standalone.sh','build.sh','policy.py','public_export_allowlist.txt'}
EXTRA={'LICENSE': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4', 'LICENSES/Apache-2.0.txt': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4', 'LICENSES/DS4-MIT.txt': '4a8a1358f5b048627d71e4988de0bafd386f4988991929629e6cb9e29b7b9b2f', 'LICENSES/DeepSeek-V41-MIT.txt': 'f2c6c602815669d292889e5be8c802f2ed950653b77999b1584e8e6aed25d040', 'LICENSES/DeepSeek-recipe-MIT.txt': 'ebb4f09972aee8608be255debaf78451a68e95c290f55c240dec2ecfa16ea6be', 'LICENSES/DeepSeek-tokenizer-MIT.txt': '6e4c38e1172f42fdbff13edf9a7a017679fb82b0fde415a3e8b3c31c6ed4a4e4', 'LICENSES/DeepSpec-MIT.txt': '474817ff0d848f0d44cea7f5ac0b488fe74f599f2a656476a94f215e5e4094c7', 'LICENSES/MULATTICE_MIT.txt': '1126322e2cc8d165adc4c792eeb195717de2bcc7b39be1ce77959d78e87ef685', 'LICENSES/PROVENANCE.md': '0306e9c5788fd9c26f2a66bb8e2094400461bcc1963cfbde22ef448b55981c2f', 'LICENSES/cgc/LICENSE': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4', 'LICENSES/hexaflake/LICENSE': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4', 'LICENSES/hexaflake/NOTICE': '7349216806d083f687ccb94fdba9738f20663e2fb5248084fc3e488178235ae3', 'LICENSES/hexaflake/licenses/CPython.txt': '78b12c3a81360b357002334f0e70ea0e92eebf7a9b358805c03c48484945f3bb', 'NOTICE': 'f93a26d22829b549b849ea471b46d7c1498abe6eb6e05decffba6e36994b7836', 'docs/PUBLICATION_CANDIDATE.md': '0031f3eb0eb6032879f8424e337c6432140f8822ea7be414ad3ce37faac88cfb', 'docs/provenance/CR6/NOTICE': '2a38179b5b97b3dc4e74d399b6a2c21bff330fbbff358a7ccf160b7b61da9144', 'docs/provenance/CR6/native/ECS_C/enrollment/PROVENANCE.md': '5889f74709894f697241e18c83f762039de579d75eadde1eff636bdb097d727c', 'docs/provenance/CR6/native/cgc/POOL_PROVENANCE.md': '5e0e0c753acfda140e9f8bb31918887d39e7dccf6dad7796149e86f8c8f0af6e', 'docs/provenance/CR6/native/cgc/PROVENANCE.md': '664f46f7d1017dc5128d4d00b9cad373265e0404bafead708dd459d9f268c6ae', 'docs/provenance/CR6/native/geodome/PROVENANCE.md': 'ec5661df10d5a23f53cffdb33dc4c0430786403050a8033378d2f183cc910c08', 'docs/provenance/CR6/native/geodome/scheduler/PROVENANCE.md': '1d693bdc8edeb02e1c3e40d0fbcc7ffea5d1bf80f562dc77fe00fe798ed7ef27', 'docs/provenance/CR6/native/geodome/state/PROVENANCE.md': '3d95f8559054b2d71be2f740cf89927f7031c10ff4aaf2c3ce028994212b5e3b', 'docs/provenance/CR6/native/runtime/cognitive_binding/PROVENANCE.md': '2865a7c0f50f00e2849cd22496f2b06d6f6b755e610054085cff74f9799ae9c4', 'docs/provenance/CR6/native/runtime/cognitive_transaction/ADAPTATION_PROVENANCE.md': '0820b2e55525b47706342d850a58079ac7661f4e3683a85ffac85487b9e240c4', 'docs/provenance/CR6/native/runtime/cognitive_transaction/COUPLED_PROVENANCE.md': '805cce8f0184dff3946b66ce563b1db02145f991e77b80f692c2236dce3a7564', 'docs/provenance/CR6/native/runtime/cognitive_transaction/PROVENANCE.md': 'ac75725a5a91ac8f2c57750cce401ea344357d1bbb486b94c798c2cc8c1e87b1', 'docs/provenance/CR6/native/runtime/cognitive_transaction/TRANSPORT_PROVENANCE.md': '0a15aad153e248d7c4113b14e702bd4924cf9ed2410071f335d6bd446da2f093'}
EXTRA.update({'docs/BUILD.md': '05f5c5e89af515c9c28dfc62ff760dabc76c7b9c4649d8251f0c3a64ba72ce7a', '.github/workflows/native.yml': 'ceaf564bf1bdb6486609ee1f154c320d0cec36d585e4449ab09484c3cb8eaad9'})
EXTRA.update({'NOTICE': '0f1a9f48c2dc52ffa6ff82ed85a84e2926900ebae59355a01b9dac87e9166f43', 'CONTRIBUTORS.md': 'ad17fb8184c325eaa48b33dbd3264fd1d57c746cdc38444fd721530bf55a0356', 'LICENSES/NATIVE_PROVENANCE.md': '02ddc189607323d41efc9cb1355e2d3befcea9520224e311d20e499f7a25ffcb'})
def sha(b):return hashlib.sha256(b).hexdigest()
def digest(p):return sha(p.read_bytes())
def manifest(b):
 out={}
 for line in b.decode().splitlines():
  h,p=line.split('  ',1);q=pathlib.PurePosixPath(p)
  assert re.fullmatch('[0-9a-f]{64}',h) and not q.is_absolute() and '..' not in q.parts and str(q)==p and p not in out and '\\' not in p,(p,h)
  out[p]=h
 return out
def files(root):
 out=set()
 for p in root.rglob('*'):
  assert not p.is_symlink() and (p.is_file() or p.is_dir()),p
  if p.is_file():out.add(p.relative_to(root).as_posix())
 return out
def component(p):
 for pre,name in [('native/geodome/','geodome'),('native/cgc/','cgc'),('native/ECS_G/','shared_cubic_math'),('native/ECS_C/session/','session'),('native/ECS_C/enrollment/','enrollment'),('native/substrate/','shared_hash'),('native/runtime/model_protocol/','model_host'),('native/runtime/','runtime_core')]:
  if p.startswith(pre):return name
 raise AssertionError(p)
def model(rows,history_sha,amendment_sha,build_sha):
 groups={}
 for p in sorted(rows):groups.setdefault(component(p),[]).append(p)
 return {'schema':'elpis.successor.system.v1','identity':{'name':'Elpis native cognitive substrate','profile':'SUCCESSOR_PUBLIC_SOURCE_CANDIDATE','publication':'SOURCE_EXPORT_AUTHORIZED','legacy_abi_v8':'SEALED_CR6_COMPATIBILITY_ONLY','model_wire_abi':1,'operator_wire_abi':1},'authority':{'legacy_commit':BASE,'parent_result_sha256':PARENT_RESULT,'source_manifest_sha256':PARENT_MANIFEST,'historical_mission_sha256':history_sha,'amendment_sha256':amendment_sha,'build_declaration_sha256':build_sha},'mission':{'division':ROLES,'neural_dataflow':'independent frozen model inference; optional asynchronous proposals and reads','native_dataflow':'guarded pipe capabilities -> serialized dispatcher -> metered native transaction -> ECS_C evidence and Geodome/CGC state','amendment_3':'PRESERVED','amendment_4':'OPERATIVE_SUCCESSOR_DEV_PROFILE','legacy_profile':'PRESERVED_SEALED_CR6'},'invariants':INVARIANTS,'limits':LIMITS,'claims':CLAIMS,'build':{'source_files':60,'native_translation_units':16,'native_dependency_files':40,'rust_compile_inputs':15,'native_archives':ARCHIVES,'legacy_root_graph':False,'elpis_dso_dependencies':0,'build_entry':'build.sh','source_root':'source','components':groups},'interfaces':{'model':['INSPECT','LOOKUP','READ_ROW','PROPOSE_ADAPT'],'operator':['STATUS','REVIEW','APPROVE','REJECT'],'operator_enrollment_wire':False,'private_rust_api':'DEV_ONLY','production_genesis':'EMPTY','observed_model_disconnect':'CANCEL_PENDING_RETAIN_COMMITTED','observed_operator_disconnect':'CANCEL_PENDING_READ_ONLY_SURVIVAL'},'publication':{'allowlist':sorted(META|set(EXTRA)|{'source/'+p for p in rows}),'unlicensed_crates':[],'public_baseline':'ba7cf4aaca6c52cc1d8f29cc5d4cdbe106f38a63','owner_authorization':True,'first_party_license_authorization':'APACHE_2_0_WITHIN_OWNER_RIGHTS','publication_authorization':True,'provenance_clearance':'OWNER_APPROVED_WITHIN_RIGHTS','source_deletion_authorized':False}}
def validate(root,expected_manifest=PARENT_MANIFEST,expected_history=HISTORY_SHA):
 assert root.is_dir() and not root.is_symlink(); b=(root/'source.sha256').read_bytes();assert sha(b)==expected_manifest
 rows=manifest(b);assert len(rows)==60 and not REMOVED&set(rows)
 assert files(root)==META|set(EXTRA)|{'source/'+p for p in rows},'package positive allowlist'
 for p,h in rows.items():assert digest(root/'source'/p)==h,p
 for p,h in EXTRA.items():assert digest(root/p)==h,p
 a=(root/'docs/AMENDMENT_4.md').read_bytes(); hist=(root/'docs/ELPIS_MISSION.md').read_bytes(); assert hist.endswith(b'\n\n'+a); hist=hist[:-len(a)-2]
 assert sha(hist)==expected_history and sha(a)==AMENDMENT_SHA and digest(root/'build_standalone.sh')==BUILD_SHA and digest(root/'build.sh')==WRAPPER_SHA,'authority/build bytes'
 d=json.loads((root/'ELPIS_SYSTEM.json').read_text());m=model(rows,sha(hist),sha(a),digest(root/'build_standalone.sh'));m['authority']['source_manifest_sha256']=expected_manifest
 assert d==m,'system authority drift'
 assert (root/'public_export_allowlist.txt').read_text()==''.join(p+'\n' for p in d['publication']['allowlist']),'export allowlist drift'
 for p in ('native/runtime/Cargo.toml','native/ECS_C/session/Cargo.toml'):
  t=tomllib.loads((root/'source'/p).read_text());assert t['package']['license']=='Apache-2.0' and t['package']['publish'] is False
 host=tomllib.loads((root/'source/native/runtime/model_protocol/Cargo.toml').read_text())['package']; assert host['publish'] is False and host['license']=='Apache-2.0'
 assert (root/'README.md').read_text()==readme(d),'README drift'
 return d

def readme(d):
 return '# Elpis native cognitive substrate — public source candidate\n\n'+ '\n'.join('- '+r for r in d['mission']['division'])+'\n\nSee `docs/ELPIS_MISSION.md` (historical text plus Amendment 4) and `ELPIS_SYSTEM.json` (live successor authority). The sealed CR6 compatibility profile retains its own contracts.\n\nThe native C/Rust runtime is a separate bounded, volatile system. No neural model is required to build it. See [offline build and CI](docs/BUILD.md) for a clean source export and a portable Linux build under a 4 GiB/no-swap scope. This is a development build, not a launcher or deployment contract. The production host needs trusted supervisor pipe capabilities; genesis is empty. No production enrollment wire exists.\n\n## Qualification scope\n\n'+ '\n'.join('- '+k+': '+v for k,v in sorted(d['claims'].items()))+'\n\nFirst-party Apache-2.0 licensing authorized within owner rights. Source export is authorized; main promotion requires successful hosted CI. Installation and deployment remain unauthorized. See `docs/PUBLICATION_CANDIDATE.md`.\n'+'\n## Contributors and licensing\n\n- [@abraxis717](https://github.com/abraxis717) (Alpharius) — Elpis development and HexaFlake computational implementation.\n- [@Akitti](https://x.com/Akitti) — contributor to Elpis through the original HexaFlake concept and geometric architecture.\n\nGeodome derives from [HexaFlake](https://github.com/abraxis717/HexaFlake). See [contributors](CONTRIBUTORS.md), [native licensing and provenance](LICENSES/NATIVE_PROVENANCE.md) and [NOTICE](NOTICE).\n'
if __name__=='__main__':
 validate(pathlib.Path(sys.argv[1]));print('SUCCESSOR_BOUNDARY=PASS')
