import yaml

from seneschal import managers


STATE_1_YAML = '''
type: sequence
cwd: output_batch_dir
zchildren:
  - type: parallel
    zchildren:
      - type: sequence
        executable: .../python3.6
        prefix_arguments: [.../topmed-1/scripts/copy_rename]
        child_type: subprocess
        zchildren:
          - arguments: [src_file1, dst_file1]
          - arguments: [src_file2, dst_file2]
      - type: parallel
        cwd: md5_dst_dir
        cores: 1
        executable: .../python3.6
        prefix_arguments: [.../topmed-1/scripts/md5_script]
        child_type: batch_job
        zchildren:
          - arguments: [src_file1, sample1]
          - arguments: [src_file2, sample2]
  - type: subprocess
    executable: .../python3.6
    arguments: [.../topmed-1/scripts/make_manifest, md5_dst_dir]
'''


STATE_2_YAML = '''
cwd: output_batch_dir
path: t
type: sequence
zchildren:
- cwd: output_batch_dir
  index: 0
  path: t/0
  type: parallel
  zchildren:
  - child_type: subprocess
    cwd: output_batch_dir
    executable: '.../python3.6'
    index: 0
    path: t/0/0
    prefix_arguments: &id001 ['.../topmed-1/scripts/copy_rename']
    type: sequence
    zchildren:
    - arguments: [src_file1, dst_file1]
      cwd: output_batch_dir
      executable: '.../python3.6'
      index: 0
      path: t/0/0/0
      prefix_arguments: *id001
      type: subprocess
    - arguments: [src_file2, dst_file2]
      cwd: output_batch_dir
      executable: '.../python3.6'
      index: 1
      path: t/0/0/1
      prefix_arguments: *id001
      type: subprocess
  - child_type: batch_job
    cores: 1
    cwd: md5_dst_dir
    executable: '.../python3.6'
    index: 1
    path: t/0/1
    prefix_arguments: &id002 ['.../topmed-1/scripts/md5_script']
    type: parallel
    zchildren:
    - arguments: [src_file1, sample1]
      cores: 1
      cwd: md5_dst_dir
      executable: '.../python3.6'
      index: 0
      path: t/0/1/0
      prefix_arguments: *id002
      type: batch_job
    - arguments: [src_file2, sample2]
      cores: 1
      cwd: md5_dst_dir
      executable: '.../python3.6'
      index: 1
      path: t/0/1/1
      prefix_arguments: *id002
      type: batch_job
- arguments: ['.../topmed-1/scripts/make_manifest', md5_dst_dir]
  cwd: output_batch_dir
  executable: '.../python3.6'
  index: 1
  path: t/1
  type: subprocess
'''

T011 = '''
arguments: [src_file2, sample2]
cores: 1
cwd: md5_dst_dir
executable: '.../python3.6'
index: 1
path: t/0/1/1
prefix_arguments: ['.../topmed-1/scripts/md5_script']
type: batch_job
'''

PATHS = '''
t
t/0
t/0/0
t/0/0/0
t/0/0/1
t/0/1
t/0/1/0
t/0/1/1
t/1
'''.split()


def test_task_inheritance():
    state = yaml.load(STATE_1_YAML)
    managers.propagate_inheritance(state)
    assert yaml.dump(state) == STATE_2_YAML[1:]


def test_index_mappings():
    state = yaml.load(STATE_2_YAML)
    index = managers.index_mappings(state)
    assert sorted(index) == PATHS
    for k, v in index.items():
        assert k == v['path']
    print(yaml.dump(index['t/0/1/1']))
    assert index['t/0/1/1'] == yaml.load(T011)
    assert index['t'] == state
