"""Tests for the flake8.style_guide.StyleGuide class."""
import optparse

import mock
import pytest

from flake8 import style_guide
from flake8 import utils
from flake8.formatting import base
from flake8.plugins import notifier


def create_options(**kwargs):
    """Create and return an instance of optparse.Values."""
    kwargs.setdefault('select', [])
    kwargs.setdefault('extended_default_select', [])
    kwargs.setdefault('ignore', [])
    kwargs.setdefault('extend_ignore', [])
    kwargs.setdefault('disable_noqa', False)
    kwargs.setdefault('enable_extensions', [])
    kwargs.setdefault('per_file_ignores', [])
    return optparse.Values(kwargs)


@pytest.mark.parametrize('select_list,ignore_list,error_code', [
    (['E111', 'E121'], [], 'E111'),
    (['E111', 'E121'], [], 'E121'),
    (['E11', 'E121'], ['E1'], 'E112'),
    (['E41'], ['E2', 'E12', 'E4'], 'E410'),
])
def test_handle_error_notifies_listeners(select_list, ignore_list, error_code):
    """Verify that error codes notify the listener trie appropriately."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    guide = style_guide.StyleGuide(create_options(select=select_list,
                                                  ignore=ignore_list),
                                   listener_trie=listener_trie,
                                   formatter=formatter)

    with mock.patch('linecache.getline', return_value=''):
        guide.handle_error(error_code, 'stdin', 1, 0, 'error found')
    error = style_guide.Violation(
        error_code, 'stdin', 1, 1, 'error found', None)
    listener_trie.notify.assert_called_once_with(error_code, error)
    formatter.handle.assert_called_once_with(error)


def test_handle_error_does_not_raise_type_errors():
    """Verify that we handle our inputs better."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    guide = style_guide.StyleGuide(create_options(select=['T111'], ignore=[]),
                                   listener_trie=listener_trie,
                                   formatter=formatter)

    assert 1 == guide.handle_error(
        'T111', 'file.py', 1, None, 'error found', 'a = 1'
    )


@pytest.mark.parametrize('select_list,ignore_list,error_code', [
    (['E111', 'E121'], [], 'E122'),
    (['E11', 'E12'], [], 'E132'),
    (['E2', 'E12'], [], 'E321'),
    (['E2', 'E12'], [], 'E410'),
    (['E111', 'E121'], ['E2'], 'E122'),
    (['E11', 'E12'], ['E13'], 'E132'),
    (['E1', 'E3'], ['E32'], 'E321'),
    (['E4'], ['E2', 'E12', 'E41'], 'E410'),
    (['E111', 'E121'], [], 'E112'),
])
def test_handle_error_does_not_notify_listeners(select_list, ignore_list,
                                                error_code):
    """Verify that error codes notify the listener trie appropriately."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    guide = style_guide.StyleGuide(create_options(select=select_list,
                                                  ignore=ignore_list),
                                   listener_trie=listener_trie,
                                   formatter=formatter)

    with mock.patch('linecache.getline', return_value=''):
        guide.handle_error(error_code, 'stdin', 1, 1, 'error found')
    assert listener_trie.notify.called is False
    assert formatter.handle.called is False


def test_style_guide_manager():
    """Verify how the StyleGuideManager creates a default style guide."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options()
    guide = style_guide.StyleGuideManager(options,
                                          listener_trie=listener_trie,
                                          formatter=formatter)
    assert guide.default_style_guide.options is options
    assert len(guide.style_guides) == 1


PER_FILE_IGNORES_UNPARSED = [
    "first_file.py:W9",
    "second_file.py:F4,F9",
    "third_file.py:E3",
    "sub_dir/*:F4",
]


@pytest.mark.parametrize('style_guide_file,filename,expected', [
    ("first_file.py", "first_file.py", True),
    ("first_file.py", "second_file.py", False),
    ("sub_dir/*.py", "first_file.py", False),
    ("sub_dir/*.py", "sub_dir/file.py", True),
    ("sub_dir/*.py", "other_dir/file.py", False),
])
def test_style_guide_applies_to(style_guide_file, filename, expected):
    """Verify that we match a file to its style guide."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options()
    guide = style_guide.StyleGuide(options,
                                   listener_trie=listener_trie,
                                   formatter=formatter,
                                   filename=style_guide_file)
    assert guide.applies_to(filename) is expected


def test_style_guide_manager_pre_file_ignores_parsing():
    """Verify how the StyleGuideManager creates a default style guide."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options(per_file_ignores=PER_FILE_IGNORES_UNPARSED)
    guide = style_guide.StyleGuideManager(options,
                                          listener_trie=listener_trie,
                                          formatter=formatter)
    assert len(guide.style_guides) == 5
    assert list(map(utils.normalize_path,
                    ["first_file.py", "second_file.py", "third_file.py",
                        "sub_dir/*"])
                ) == [g.filename for g in guide.style_guides[1:]]


@pytest.mark.parametrize('ignores,violation,filename,handle_error_return', [
    (['E1', 'E2'], 'F401', 'first_file.py', 1),
    (['E1', 'E2'], 'E121', 'first_file.py', 0),
    (['E1', 'E2'], 'F401', 'second_file.py', 0),
    (['E1', 'E2'], 'F401', 'third_file.py', 1),
    (['E1', 'E2'], 'E311', 'third_file.py', 0),
    (['E1', 'E2'], 'F401', 'sub_dir/file.py', 0),
])
def test_style_guide_manager_pre_file_ignores(ignores, violation, filename,
                                              handle_error_return):
    """Verify how the StyleGuideManager creates a default style guide."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options(ignore=ignores,
                             select=['E', 'F', 'W'],
                             per_file_ignores=PER_FILE_IGNORES_UNPARSED)
    guide = style_guide.StyleGuideManager(options,
                                          listener_trie=listener_trie,
                                          formatter=formatter)
    assert (guide.handle_error(violation, filename, 1, 1, "Fake text")
            == handle_error_return)


@pytest.mark.parametrize('filename,expected', [
    ('first_file.py', utils.normalize_path('first_file.py')),
    ('second_file.py', utils.normalize_path('second_file.py')),
    ('third_file.py', utils.normalize_path('third_file.py')),
    ('fourth_file.py', None),
    ('sub_dir/__init__.py', utils.normalize_path('sub_dir/*')),
    ('other_dir/__init__.py', None),
])
def test_style_guide_manager_style_guide_for(filename, expected):
    """Verify the style guide selection function."""
    listener_trie = mock.create_autospec(notifier.Notifier, instance=True)
    formatter = mock.create_autospec(base.BaseFormatter, instance=True)
    options = create_options(per_file_ignores=PER_FILE_IGNORES_UNPARSED)
    guide = style_guide.StyleGuideManager(options,
                                          listener_trie=listener_trie,
                                          formatter=formatter)

    file_guide = guide.style_guide_for(filename)
    assert file_guide.filename == expected
