from gramex.config import variables
import numpy as np
from gramex import cache
import os
from pydoc import locate
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model.base import LinearClassifierMixin
from sklearn import naive_bayes as nb
from sklearn.tree import plot_tree,  DecisionTreeClassifier
from tornado.template import Template
import json
import matplotlib.pyplot as plt
from scipy.stats import norm

op = os.path
DIR = variables['GRAMEXDATA'] + '/apps/mlhandler'
if not op.isdir(DIR):
    os.mkdir(DIR)


def init_form(handler):
    """Process input from the landing page and write the current session config."""
    data_file = handler.request.files.get('data-file', [{}])[0]
    # TODO: Unix filenames may not be valid Windows filenames.
    outpath = op.join(DIR, "data.csv")
    with open(outpath, 'wb') as fout:
        fout.write(data_file['body'])
    return 'OK'


def _make_gnb_chart(clf, dfx):
    plt.close('all')

    n_classes, n_feats = clf.theta_.shape
    std = np.sqrt(clf.sigma_)
    fig, ax = plt.subplots(nrows=n_classes, ncols=n_feats, sharex=True)
    for i in range(n_classes):
        for j in range(n_feats):
            loc = clf.theta_[i, j]
            scale = std[i, j]
            p = norm(loc, scale)
            x = np.linspace(norm.ppf(0.01), norm.ppf(0.99), 100)  # noqa: E912
            y = p.pdf(x)
            ax[i, j].plot(x, y)
            ax[i, j].fill_between(x, y, where=y > 0)
            if i < (n_classes - 1):
                ax[i, j].tick_params(axis='x', bottom=False)
    for i, _ax in enumerate(ax[:, -1]):
        _ax.set_ylabel(clf.classes_[i])
        _ax.yaxis.set_label_position('right')
    for i, _ax in enumerate(ax[0, :]):
        _ax.set_xlabel(dfx.columns[i])
        _ax.xaxis.set_label_position('top')
    plt.tight_layout()
    plt.savefig('chart.png')


def _plot_decision_tree(clf, dfx):
    plt.close('all')
    fig, ax = plt.subplots()
    plot_tree(clf, filled=True, ax=ax)
    plt.savefig('chart.png')


def _make_chart(clf, df):
    if isinstance(clf, (LinearClassifierMixin, nb.MultinomialNB)):
        with open('linear_model.json', 'r', encoding='utf8') as fout:
            spec = json.load(fout)
        cdf = pd.DataFrame(clf.coef_, columns=df.columns)
        cdf['class'] = clf.classes_
        cdf = pd.melt(cdf, id_vars='class')
        spec['data']['values'] = cdf.to_dict(orient='records')
        return json.dumps(spec)
    if isinstance(clf, nb.GaussianNB):
        _make_gnb_chart(clf, df)
        return True
    if isinstance(clf, DecisionTreeClassifier):
        _plot_decision_tree(clf, df)
        return True
    return False


def fit(handler):
    kwargs = json.loads(handler.request.body)
    url = kwargs['url'].replace('$GRAMEXDATA', variables['GRAMEXDATA'])
    df = cache.open(url)
    clf = locate(kwargs['model_class'])()
    test_size = float(kwargs['testSize']) / 100
    target_col = kwargs['output']
    dfy = df[target_col]
    dfx = df[[c for c in df if c != target_col]]
    x, y = dfx.values, dfy.values
    xtrain, xtest, ytrain, ytest = train_test_split(
            x, y, test_size=test_size, shuffle=True, stratify=y)
    clf.fit(xtrain, ytrain)
    score = clf.score(xtest, ytest)
    with open('report.html', 'r', encoding='utf8') as fout:
        tmpl = Template(fout.read())
    viz = _make_chart(clf, dfx)
    return tmpl.generate(score=score, model=clf, spec=viz)
