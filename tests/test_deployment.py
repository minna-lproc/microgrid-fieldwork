from pathlib import Path
import importlib.util
import pytest

SPEC=importlib.util.spec_from_file_location('deployment',Path(__file__).resolve().parents[1]/'scripts/deploy_pythonanywhere.py')
deployment=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deployment)
SHA='a'*40


def test_allowlist_preserves_data_and_cache_parity(tmp_path):
    for name,content in {
        'app.py':'# app',
        'templates/index.html':'hello',
        'static/app.js':"const name='gridfield-shell-v3';",
        'static/sw.js':"const name='gridfield-shell-v3';",
        'instance/survey.sqlite':'private-survey-records',
        'instance/secret.key':'private-key',
        '.env':'private-env',
        'tests/test_app.py':'# not deployed',
    }.items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
    files=deployment.prepare_files(tmp_path,SHA)
    assert set(files)=={'app.py','templates/index.html','static/app.js','static/sw.js'}
    assert b'gridfield-shell-aaaaaaaaaaaaaaaa' in files['static/app.js']
    assert b'gridfield-shell-aaaaaaaaaaaaaaaa' in files['static/sw.js']
    assert (tmp_path/'instance/survey.sqlite').read_text()=='private-survey-records'


def test_dependency_comparison_accepts_windows_line_endings():
    assert deployment.requirements_signature(b'Flask==3.1.3\r\n# comment\r\n')==deployment.requirements_signature(b'Flask==3.1.3\n')
    assert deployment.requirements_signature(b'Flask==3.1.3\n')!=deployment.requirements_signature(b'Flask==3.1.2\n')


def test_rejects_non_git_revision(tmp_path):
    with pytest.raises(ValueError,match='commit SHA'):
        deployment.prepare_files(tmp_path,'main; dangerous')
