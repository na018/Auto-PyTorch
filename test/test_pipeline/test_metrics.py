import numpy as np

import pytest

import sklearn.metrics


from autoPyTorch.constants import (
    BINARY,
    CONTINUOUS,
    OUTPUT_TYPES_TO_STRING,
    STRING_TO_TASK_TYPES,
    TABULAR_CLASSIFICATION,
    TABULAR_REGRESSION,
    TASK_TYPES_TO_STRING
)
from autoPyTorch.metrics import accuracy
from autoPyTorch.pipeline.components.training.metrics.base import (
    _PredictMetric,
    _ThresholdMetric,
    autoPyTorchMetric,
    make_metric,
)
from autoPyTorch.pipeline.components.training.metrics.utils import calculate_score, get_metrics


@pytest.mark.parametrize('output_type', ['multiclass',
                                         'multiclass-multioutput',
                                         'binary'])
def test_get_no_name_classification(output_type):
    dataset_properties = {'task_type': 'tabular_classification',
                          'output_type': output_type}
    metrics = get_metrics(dataset_properties)
    for metric in metrics:
        assert isinstance(metric, autoPyTorchMetric)


@pytest.mark.parametrize('output_type', ['continuous', 'continuous-multioutput'])
def test_get_no_name_regression(output_type):
    dataset_properties = {'task_type': 'tabular_regression',
                          'output_type': output_type}
    metrics = get_metrics(dataset_properties)
    for metric in metrics:
        assert isinstance(metric, autoPyTorchMetric)


@pytest.mark.parametrize('metric', ['accuracy', 'average_precision',
                                    'balanced_accuracy', 'f1'])
def test_get_name(metric):
    dataset_properties = {'task_type': TASK_TYPES_TO_STRING[TABULAR_CLASSIFICATION],
                          'output_type': OUTPUT_TYPES_TO_STRING[BINARY]}
    metrics = get_metrics(dataset_properties, [metric])
    for i in range(len(metrics)):
        assert isinstance(metrics[i], autoPyTorchMetric)
        assert metrics[i].name.lower() == metric.lower()


def test_get_name_error():
    dataset_properties = {'task_type': TASK_TYPES_TO_STRING[TABULAR_CLASSIFICATION],
                          'output_type': OUTPUT_TYPES_TO_STRING[BINARY]}
    names = ['root_mean_sqaured_error', 'average_precision']
    with pytest.raises(ValueError, match=r"Invalid name entered for task [a-z]+_[a-z]+, "):
        get_metrics(dataset_properties, names)


def test_classification_metrics():
    # test of all classification metrics
    dataset_properties = {'task_type': TASK_TYPES_TO_STRING[TABULAR_CLASSIFICATION],
                          'output_type': OUTPUT_TYPES_TO_STRING[BINARY]}
    y_target = np.array([0, 1, 0, 1])
    y_pred = np.array([0, 0, 0, 1])
    metrics = get_metrics(dataset_properties=dataset_properties, all_supported_metrics=True)
    score_dict = calculate_score(y_pred, y_target, STRING_TO_TASK_TYPES[dataset_properties['task_type']], metrics)
    assert isinstance(score_dict, dict)
    for name, score in score_dict.items():
        assert isinstance(name, str)
        assert isinstance(score, float)


def test_regression_metrics():
    # test of all regression metrics
    dataset_properties = {'task_type': TASK_TYPES_TO_STRING[TABULAR_REGRESSION],
                          'output_type': OUTPUT_TYPES_TO_STRING[CONTINUOUS]}
    y_target = np.array([0.1, 0.6, 0.7, 0.4])
    y_pred = np.array([0.6, 0.7, 0.4, 1])
    metrics = get_metrics(dataset_properties=dataset_properties, all_supported_metrics=True)
    score_dict = calculate_score(y_pred, y_target, STRING_TO_TASK_TYPES[dataset_properties['task_type']], metrics)

    assert isinstance(score_dict, dict)
    for name, score in score_dict.items():
        assert isinstance(name, str)
        assert isinstance(score, float)


def test_predictmetric_binary():
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])

    scorer = _PredictMetric(
        'accuracy', sklearn.metrics.accuracy_score, 1, 0, 1, {})

    score = scorer(y_true, y_pred)
    assert score == pytest.approx(1.0)

    y_pred = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
    score = scorer(y_true, y_pred)
    assert score == pytest.approx(0.5)

    y_pred = np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0], [1.0, 1.0]])
    score = scorer(y_true, y_pred)
    assert score == pytest.approx(0.5)

    scorer = _PredictMetric(
        'bac', sklearn.metrics.balanced_accuracy_score,
        1, 0, 1, {})

    score = scorer(y_true, y_pred)
    assert score, pytest.approx(0.5)

    scorer = _PredictMetric(
        'accuracy', sklearn.metrics.accuracy_score, 1, 0, -1, {})

    y_pred = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    score = scorer(y_true, y_pred)
    assert score == pytest.approx(-1.0)


def test_threshold_scorer_binary():
    y_true = [0, 0, 1, 1]
    y_pred = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])

    scorer = _ThresholdMetric(
        'roc_auc', sklearn.metrics.roc_auc_score, 1, 0, 1, {})

    score = scorer(y_true, y_pred)
    assert score == pytest.approx(1.0)

    y_pred = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
    score = scorer(y_true, y_pred)
    assert score == pytest.approx(0.5)

    y_pred = np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0], [1.0, 1.0]])
    score = scorer(y_true, y_pred)
    assert score == pytest.approx(0.5)

    scorer = _ThresholdMetric(
        'roc_auc', sklearn.metrics.roc_auc_score, 1, 0, -1, {})

    y_pred = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    score = scorer(y_true, y_pred)
    assert score == pytest.approx(-1.0)


def test_sign_flip():
    y_true = np.arange(0, 1.01, 0.1)
    y_pred = y_true.copy()

    scorer = make_metric(
        'r2', sklearn.metrics.r2_score, greater_is_better=True)

    score = scorer(y_true, y_pred + 1.0)
    assert score == pytest.approx(-9.0)

    score = scorer(y_true, y_pred + 0.5)
    assert score == pytest.approx(-1.5)

    score = scorer(y_true, y_pred)
    assert score == pytest.approx(1.0)

    scorer = make_metric(
        'r2', sklearn.metrics.r2_score, greater_is_better=False)

    score = scorer(y_true, y_pred + 1.0)
    assert score == pytest.approx(9.0)

    score = scorer(y_true, y_pred + 0.5)
    assert score == pytest.approx(1.5)

    score = scorer(y_true, y_pred)
    assert score == pytest.approx(-1.0)


def test_classification_only_metric():
    y_true = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    y_pred = \
        np.array([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    scorer = accuracy

    score = calculate_score(y_true, y_pred, TABULAR_CLASSIFICATION, [scorer])

    previous_score = scorer._optimum
    assert score['accuracy'] == pytest.approx(previous_score)
