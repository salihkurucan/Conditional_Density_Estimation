import scipy.stats as stats
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from density_simulation import ConditionalDensity

class EconDensity(ConditionalDensity):
  """
  The economy dataset generated by the function y=x2 + N(0,self.std). Inherits ConditionalDensity class.
  """

  def __init__(self, std=1):
    self.std = std
    self.ndim_x = 1
    self.ndim_y = 1
    self.ndim = self.ndim_x + self.ndim_y

  def pdf(self, X, Y):
    mean = X**2
    return np.where(X<0, 0, stats.norm.pdf(Y, loc=mean, scale=self.std))

  def cdf(self, X, Y):
    mean = X ** 2
    return np.where(X<0, 0, stats.norm.cdf(Y, loc=mean, scale=self.std))

  def joint_pdf(self, X, Y):
    raise NotImplementedError

  def simulate_conditional(self, X):
    if X.ndim == 2 and X.shape[1]:
      X = X.flatten()
    assert X.ndim == 1

    n_samples = X.shape[0]
    Y = X ** 2 + np.random.normal(loc=0, scale=self.std, size=n_samples)
    X = np.expand_dims(X, axis=1)
    Y = np.expand_dims(Y, axis=1)
    return X, Y

  def simulate(self, n_samples=1000):
    assert n_samples > 0
    X = np.abs(np.random.standard_normal(size=[n_samples]))
    Y = X ** 2 + np.random.normal(loc=0, scale=self.std, size=n_samples)
    return X, Y


  def __str__(self):
    return str("\nProbabilistic model type: {}\n std: {}\n n_dim_x: {}\n n_dim_y: {}\n".format(self.__class__.__name__, self.std, self.ndim_x,
                                                                                                 self.ndim_y))

  def __unicode__(self):
    return self.__str__().encode("utf-8")