"""Transport import rejects bad registrations before changing installed artwork."""

import hashlib
import json

from PIL import Image
import pytest

from devtools.import_transport_media import import_transport_media


@pytest.fixture
def delivery(tmp_path):
    source, preserved, production, repo = (tmp_path / name for name in ('source','archive','production','repo'))
    source.mkdir()
    production.mkdir()
    Image.new('RGBA',(4,4),(80,160,220,255)).save(source/'page.png')
    layer={'pages':['page.png'],'frames':[{'page':0,'source':[0,0,4,4],'offset':[0,0]}]}
    row={'fps':32,'frames':1,'cell':4,'pivot':[2,3],'palette':['50a0dc'],
         'cameras':{str(q):{'layers':{'back':layer,'front':layer}} for q in range(4)}}
    (source/'manifest.json').write_text(json.dumps(row))
    (source/'SHA256SUMS').write_text(hashlib.sha256((source/'page.png').read_bytes()).hexdigest()+'  page.png\n')
    (production/'art-manifest.json').write_text('{"files":[],"total_bytes":0}')
    return source,preserved,production,repo


@pytest.mark.parametrize('defect',('late-crop','late-page','palette','archive-conflict','source-checksum'))
def test_rejected_bank_does_not_publish_partial_artwork(delivery,defect):
    source,preserved,production,repo=delivery
    before=(production/'art-manifest.json').read_bytes()
    row=json.loads((source/'manifest.json').read_text())
    if defect=='late-crop':
        row['cameras']['3']['layers']['front']['frames'][0]['source']=[2,0,4,4]
    elif defect=='late-page':
        row['cameras']['3']['layers']['front']['frames'][0]['page']=1
    elif defect=='palette':
        row['palette']=['invalid']
    elif defect=='archive-conflict':
        preserved.mkdir()
        (preserved/'manifest.json').write_text('earlier source')
    else:
        (source/'page.png').write_bytes(b'changed source')
    (source/'manifest.json').write_text(json.dumps(row))
    with pytest.raises(ValueError):
        import_transport_media(source,preserved=preserved,production=production,repo=repo,program='dimension_door')
    assert (production/'art-manifest.json').read_bytes()==before
    assert not (production/'game').exists()
    assert not repo.exists()
    assert not (preserved/'page.png').exists()


def test_repeat_keeps_source_pixels_and_selected_spell_recipe(delivery):
    source,preserved,production,repo=delivery
    import_transport_media(source,preserved=preserved,production=production,repo=repo,program='dimension_door')
    recipe=repo/'game/data/transport_media/transport-draft.json'
    recipe.write_text('already selected recipe')
    import_transport_media(source,preserved=preserved,production=production,repo=repo,program='dimension_door')
    assert recipe.read_text()=='already selected recipe'
    original=(source/'page.png').read_bytes()
    assert (preserved/'page.png').read_bytes()==original
    assert (repo/'game/assets/transport_media/page.png').read_bytes()==original
