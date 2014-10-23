#! /usr/bin/env python

import argparse
import csv
from pprint import pprint
from time import time

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.datasets.base import Bunch
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.grid_search import GridSearchCV
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import LabelEncoder, StandardScaler, Binarizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression


def fetch_gitlog(data_path, collapse=None, stats=False):
    """Convert the CSV log into a datase suitable for scikit-learn."""
    description = 'Lageled git log history'

    with open(data_path, 'rb') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',', quotechar='"',
                               doublequote=True)
        next(csvreader)
        # Summary, Message, Number of Files, Total Lines, Added Lines, Deleted Lines, Label, SHA-1
        full_dataset = [(line[0].strip(), line[1].strip(),
                         int(line[2]), int(line[3]), int(line[4]),
                         int(line[5]), line[6], line[7]) for line in csvreader]

        data = np.array([d for d in full_dataset if d[6]])

        collapse = {} if not collapse else collapse
        for key, value in collapse.items():
            data[data[:, 6] == key, 6] = value

        # Encode targets into numbers
        target = [d[6] for d in data]
        le = LabelEncoder()
        le.fit(target)
        target_names = le.classes_
        target = le.transform(target)

        if stats:
            print 'Original dataset [%d]' % len(full_dataset)
            print 'Labeled dataset [%d]' % len(data)
            print 'Ratio [%2.2f%%]' % (100.0 * len(data) / len(full_dataset))

    return Bunch(filename=data_path,
                 data=data,
                 target_names=target_names,
                 target=target,
                 DESCR=description)


class SliceFeature(BaseEstimator):
    """Estimator to slice a feature."""

    def __init__(self, slc, astype=None):
        """Build an instance using a slice object.

        >>> X = np.array([[1, 2, 3], [10, 20, 30]])
        >>> X
        array([[ 1,  2,  3],
               [10, 20, 30]])

        >>> slc = SliceFeature(slice(0, 1))
        >>> slc.transform(X)
        array([ 1, 10])

        >>> slc = SliceFeature(slice(0, 2))
        >>> slc.transform(X)
        array([[ 1,  2],
               [10, 20]])

        """
        self.slc = slc
        self.astype = astype

    def fit(self, X, y=None):
        """Does nothing: this transformer is stateless."""
        return self

    def transform(self, X, y=None):
        """Does nothing: this transformer is stateless."""
        if self.slc.step:
            index = range(self.slc.start, self.slc.stop, self.slc.step)
        else:
            index = range(self.slc.start, self.slc.stop)

        result = X[:, index]
        if len(index) == 1:
            result = result.reshape(X.shape[0])

        if self.astype:
            result = result.astype(self.astype)

        return result


class Densifier(BaseEstimator):
    def fit(self, X, y=None):
        pass

    def fit_transform(self, X, y=None):
        return self.transform(X)

    def transform(self, X, y=None):
        return X.toarray()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train different models with the same dataset.')
    parser.add_argument('-c', '--csv', help='csv file name')

    args = parser.parse_args()

    if not args.csv:
        parser.print_help()
        exit(1)

    pipeline_summary = Pipeline([
        ('slice', SliceFeature(slice(0, 1))),
        ('vect', CountVectorizer(stop_words='english')),
        # ('binary', Binarizer()),
        ('tfidf', TfidfTransformer()),
    ])

    pipeline_message = Pipeline([
        ('slice', SliceFeature(slice(1, 2))),
        ('vect', CountVectorizer(stop_words='english')),
        # ('binary', Binarizer()),
        ('tfidf', TfidfTransformer()),
    ])

    pipeline_numeric = Pipeline([
        ('slice', SliceFeature(slice(2, 6), astype=int)),
    ])

    main_pipeline = Pipeline([
        ('features', FeatureUnion([
            ('summary', pipeline_summary),
            ('message', pipeline_message),
            ('numeric', pipeline_numeric),
        ])),
        # ('densifier', Densifier()),
        # ('scaler', StandardScaler(with_mean=False)),
        # ('scaler', StandardScaler()),
        # ('clf', LinearSVC()),
        # ('pca', PCA(n_components=100)),
        ('clf', LogisticRegression()),
    ])

    parameters = {
        'features__summary__vect__max_df': (0.5, 0.75, 1.0),
        'features__summary__vect__max_features': (None, 5000, 10000, 50000),
        'features__summary__vect__ngram_range': ((1, 1), (1, 2)),  # unigrams or bigrams
        # 'features__summary__tfidf__use_idf': (True, False),
        # 'features__summary__tfidf__norm': ('l1', 'l2'),
        'features__message__vect__max_df': (0.5, 0.75, 1.0),
        'features__message__vect__max_features': (None, 5000, 10000, 50000),
        'features__message__vect__ngram_range': ((1, 1), (1, 2)),  # unigrams or bigrams
        # 'features__message__tfidf__use_idf': (True, False),
        # 'features__message__tfidf__norm': ('l1', 'l2'),
        # 'clf__C': (0.0001, 0.001, 0.01, 0.1, 1.0),
        # 'clf__loss': ('l1', 'l2'),
        # 'clf__penalty': ('l1', 'l2'),
        # 'clf__dual': (True, False),
        # 'clf__tol': (1e-4),
        # 'clf__multi_class': ('ovr', 'crammer_singer'),
        # 'clf__fit_intercept': (True, False),
        # 'clf__intercept_scaling': (0.0001, 0.001, 0.01, 0.1, 1.0),
    }
    grid_search = GridSearchCV(main_pipeline, parameters, n_jobs=-1, verbose=1)

    print 'Performing grid search...'
    print 'pipeline:', [name for name, _ in main_pipeline.steps]
    print 'parameters:'
    pprint(parameters)

    collapse_map = {
        'Fix (Minor)': 'Fix',
        'Fix (Major)': 'Fix',
        'Regression (Minor)': 'Regression',
        'Regression (Major)': 'Regression',
        'Refactoring (Minor)': 'Refactoring',
        'Refactoring (Major)': 'Refactoring',
        'Feature (Minor)': 'Feature',
        'Feature (Major)': 'Feature',
        'Documentation (Minor)': 'Documentation',
        'Documentation (Major)': 'Documentation',
    }
    data = fetch_gitlog(args.csv, collapse=collapse_map, stats=True)

    t0 = time()
    grid_search.fit(data.data, data.target)
    print 'done in %0.3fs' % (time() - t0)
    print

    print 'Best score: %0.3f' % grid_search.best_score_
    print 'Best parameters set:'
    best_parameters = grid_search.best_estimator_.get_params()
    for param_name in sorted(parameters.keys()):
        print '\t%s: %r' % (param_name, best_parameters[param_name])
