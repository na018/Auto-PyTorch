
"""
======================
Ensemble from random search
---------------------------

This is a temporal example to make sure that ensemble works.
It also sets how SMAC should create the output information,
so that the ensemble builder works.

We will remove this file, once SMAC + ensemble builder work
======================
"""
import copy
import tempfile
import time
import typing

import dask
import dask.distributed

import numpy as np

import sklearn.datasets
import sklearn.model_selection
from sklearn.metrics import accuracy_score

from autoPyTorch.constants import MULTICLASS, TABULAR_CLASSIFICATION
from autoPyTorch.datasets.tabular_dataset import TabularDataset
from autoPyTorch.ensemble.ensemble_builder import EnsembleBuilderManager
from autoPyTorch.pipeline.components.training.metrics.metrics import accuracy
from autoPyTorch.pipeline.tabular_classification import TabularClassificationPipeline
from autoPyTorch.utils.backend import Backend, create
from autoPyTorch.utils.pipeline import get_dataset_requirements


def get_data_to_train(backend: Backend) -> typing.Tuple[typing.Dict[str, typing.Any]]:
    """
    This function returns a fit dictionary that within itself, contains all
    the information to fit a pipeline
    """

    # Get the training data for tabular classification
    # Move to Australian to showcase numerical vs categorical
    X, y = sklearn.datasets.fetch_openml(data_id=40981, return_X_y=True, as_frame=True)
    X_train, X_test, y_train, y_test = sklearn.model_selection.train_test_split(
        X,
        y,
        random_state=1,
        test_size=0.2,
    )

    train_indices, val_indices = sklearn.model_selection.train_test_split(
        list(range(X_train.shape[0])),
        random_state=1,
        test_size=0.25,
    )

    # Create a datamanager for this toy problem
    datamanager = TabularDataset(
        X=X_train, Y=y_train,
        X_test=X_test, Y_test=y_test,
    )
    backend.save_datamanager(datamanager)

    info = {'task_type': datamanager.task_type,
            'output_type': datamanager.output_type,
            'issparse': datamanager.issparse,
            'numerical_columns': datamanager.numerical_columns,
            'categorical_columns': datamanager.categorical_columns}
    dataset_properties = datamanager.get_dataset_properties(get_dataset_requirements(info))

    # Fit the pipeline
    fit_dictionary = {
        'X_train': X_train,
        'y_train': y_train,
        'train_indices': train_indices,
        'val_indices': val_indices,
        'X_test': X_test,
        'y_test': y_test,
        'dataset_properties': dataset_properties,
        # Training configuration
        'job_id': 'example_ensemble_1',
        'working_dir': './tmp/example_ensemble_1',  # Hopefully generated by backend
        'device': 'cpu',
        'runtime': 100,
        'torch_num_threads': 1,
        'early_stopping': 20,
        'use_tensorboard_logger': True,
        'use_pynisher': False,
        'memory_limit': 4096,
        'metrics_during_training': True,
        'seed': 0,
        'budget_type': 'epochs',
        'epochs': 10.0,
        'split_id': 0,
        'backend': backend,
    }

    return fit_dictionary


def random_search_and_save(fit_dictionary: typing.Dict[str, typing.Any], backend: Backend,
                           num_models: int) -> None:
    """
    A function to generate randomly fitted pipelines.
    It inefficiently pass the data in the fit dictionary, as there is no datamanager yet.

    It uses the backend to save the models and predictions for the ensemble selection
    """

    # Ensemble selection will evaluate performance on the OOF predictions. Store the OOF
    # Ground truth
    datamanager = backend.load_datamanager()
    X_train, y_train = datamanager.train_tensors
    X_test, y_test = (None, None)
    if datamanager.test_tensors is not None:
        X_test, y_test = datamanager.test_tensors
    targets = np.take(y_train, fit_dictionary['val_indices'], axis=0)
    backend.save_targets_ensemble(targets)

    for idx in range(num_models):
        pipeline = TabularClassificationPipeline(
            dataset_properties=fit_dictionary['dataset_properties'])

        # Sample a random configuration
        pipeline_cs = pipeline.get_hyperparameter_search_space()
        config = pipeline_cs.sample_configuration()
        pipeline.set_hyperparameters(config)

        # Fit the sample configuration
        pipeline.fit(fit_dictionary)

        # Predict using the fit model
        ensemble_predictions = pipeline.predict(
            X_train.iloc[fit_dictionary['val_indices']]
        )
        test_predictions = pipeline.predict(X_test)

        backend.save_numrun_to_dir(
            seed=fit_dictionary['seed'],
            idx=idx,
            budget=fit_dictionary['epochs'],
            model=pipeline,
            cv_model=None,
            ensemble_predictions=ensemble_predictions,
            valid_predictions=None,
            test_predictions=test_predictions,
        )

        score = accuracy_score(y_test, np.argmax(test_predictions, axis=1))
        print(f"Fitted a pipeline {idx} with score = {score}")

    return


if __name__ == "__main__":

    # Build a repository with random fitted models
    backend = create(temporary_directory='./tmp/autoPyTorch_ensemble_test_tmp',
                     output_directory='./tmp/autoPyTorch_ensemble_test_out',
                     delete_tmp_folder_after_terminate=False)

    # Create the directory structure
    backend._make_internals_directory()

    # Get data to train
    fit_dictionary = get_data_to_train(backend)

    # Create some random models for the ensemble
    random_search_and_save(fit_dictionary, backend, num_models=1)

    # Build a ensemble from the above components
    # Use dak client here to make sure this is proper working,
    # as with smac we will have to use a client
    dask.config.set({'distributed.worker.daemon': False})
    dask_client = dask.distributed.Client(
        dask.distributed.LocalCluster(
            n_workers=2,
            processes=True,
            threads_per_worker=1,
            # We use the temporal directory to save the
            # dask workers, because deleting workers
            # more time than deleting backend directories
            # This prevent an error saying that the worker
            # file was deleted, so the client could not close
            # the worker properly
            local_directory=tempfile.gettempdir(),
        )
    )
    manager = EnsembleBuilderManager(
        start_time=time.time(),
        time_left_for_ensembles=100,
        backend=copy.deepcopy(backend),
        dataset_name=fit_dictionary['job_id'],
        output_type=MULTICLASS,
        task_type=TABULAR_CLASSIFICATION,
        metrics=[accuracy],
        opt_metric='accuracy',
        ensemble_size=50,
        ensemble_nbest=50,
        max_models_on_disc=50,
        seed=fit_dictionary['seed'],
        max_iterations=1,
        read_at_most=np.inf,
        ensemble_memory_limit=fit_dictionary['memory_limit'],
        random_state=fit_dictionary['seed'],
        precision=32,
    )
    manager.build_ensemble(dask_client)
    future = manager.futures.pop()
    dask.distributed.wait([future])  # wait for the ensemble process to finish
    print(f"Ensemble build it: {future.result()}")
