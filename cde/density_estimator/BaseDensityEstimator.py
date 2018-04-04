from sklearn.model_selection import GridSearchCV
import warnings
from scipy.stats import multivariate_normal
#matplotlib.use("PS") #handles X11 server detection (required to run on console)
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm

from cde import ConditionalDensity

from cde.helpers import *

class BaseDensityEstimator(ConditionalDensity):
  """ Interface for conditional density estimation models """

  def fit(self, X, Y):
    """ Fits the conditional density model with provided data

      Args:
        X: numpy array to be conditioned on - shape: (n_samples, n_dim_x)
        Y: numpy array of y targets - shape: (n_samples, n_dim_y)
        n_folds: number of cross-validation folds (positive integer)

    """
    raise NotImplementedError

  def pdf(self, X, Y):
    """ Predicts the conditional likelihood p(y|x). Requires the model to be fitted.

       Args:
         X: numpy array to be conditioned on - shape: (n_samples, n_dim_x)
         Y: numpy array of y targets - shape: (n_samples, n_dim_y)

       Returns:
          conditional likelihood p(y|x) - numpy array of shape (n_query_samples, )

     """
    raise NotImplementedError

  def predict_density(self, X, Y=None, resolution=50):
    """ Computes conditional density p(y|x) over a predefined grid of y target values

      Args:
        X: values/vectors to be conditioned on - shape: (n_instances, n_dim_x)
        Y: (optional) y values to be evaluated from p(y|x) -  if not set, Y will be a grid with with specified resolution
        resulution: integer specifying the resolution of evaluation_runs grid

      Returns: tuple (P, Y)
         - P - density p(y|x) - shape (n_instances, resolution**n_dim_y)
         - Y - grid with with specified resolution - shape (resolution**n_dim_y, n_dim_y) or a copy of Y \
           in case it was provided as argument
    """
    raise NotImplementedError

  def _param_grid(self):
    raise NotImplementedError

  def score(self, X, Y):
    """Computes the mean conditional log-likelihood of the provided data (X, Y)

    Args:
      X: numpy array to be conditioned on - shape: (n_query_samples, n_dim_x)
      Y: numpy array of y targets - shape: (n_query_samples, n_dim_y)

    Returns:
      negative log likelihood of data
    """
    if hasattr(self, 'log_pdf'):
      return(np.mean(self.log_pdf(X, Y)))
    else:
      X, Y = self._handle_input_dimensionality(X, Y, fitting=False)

      assert self.fitted, "model must be fitted to compute likelihood score"
      with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # don't print division by zero warning
        conditional_log_likelihoods = np.log(self.pdf(X, Y))
      return np.mean(conditional_log_likelihoods)

  def mean_(self, x_cond):
    """ Mean of the fitted distribution conditioned on x_cond
    Args:
      x_cond: different x values to condition on - numpy array of shape (n_values, ndim_x)

    Returns:
      Means E[y|x] corresponding to x_cond - numpy array of shape (n_values, ndim_y)
    """
    assert self.fitted, "model must be fitted"
    assert x_cond.ndim == 2

    if self.can_sample:
      return self._mean_mc(x_cond)
    else:
      return self._mean_pdf(x_cond)

  def covariance(self, x_cond):
    """ Covariance of the fitted distribution conditioned on x_cond

    Args:
      x_cond: different x values to condition on - numpy array of shape (n_values, ndim_x)

    Returns:
      Covariances Cov[y|x] corresponding to x_cond - numpy array of shape (n_values, ndim_y, ndim_y)
    """
    assert self.fitted, "model must be fitted"
    return self._covariance_pdf(x_cond)

  def value_at_risk(self, x_cond, alpha=0.01):
    """ Computes the Value-at-Risk (VaR) of the fitted distribution. Only if ndim_y = 1

    Args:
      x_cond: different x values to condition on - numpy array of shape (n_values, ndim_x)
      alpha: quantile percentage of the distribution

    Returns:
       VaR values for each x to condition on - numpy array of shape (n_values)
    """
    assert self.fitted, "model must be fitted"
    assert self.ndim_y == 1, "Value at Risk can only be computed when ndim_y = 1"
    assert x_cond.ndim == 2

    if self.has_cdf:
      return self._value_at_risk_cdf(x_cond, alpha=alpha)
    elif self.can_sample:
      return self._value_at_risk_mc(x_cond, alpha=alpha)
    else:
      raise NotImplementedError()

  def conditional_value_at_risk(self, x_cond, alpha=0.01):
    """ Computes the Conditional Value-at-Risk (CVaR) / Expected Shortfall of the fitted distribution. Only if ndim_y = 1

       Args:
         x_cond: different x values to condition on - numpy array of shape (n_values, ndim_x)
         alpha: quantile percentage of the distribution

       Returns:
         CVaR values for each x to condition on - numpy array of shape (n_values)
       """
    assert self.fitted, "model must be fitted"
    assert self.ndim_y == 1, "Value at Risk can only be computed when ndim_y = 1"
    assert x_cond.ndim == 2

    if self.can_sample:
      return self._conditional_value_at_risk_mc(x_cond, alpha=alpha)
    else:
      raise NotImplementedError()

  def fit_by_cv(self, X, Y, n_folds=5, param_grid=None):
    """ Fits the conditional density model with hyperparameter search and cross-validation.

    - Determines the best hyperparameter configuration from a pre-defined set using cross-validation. Thereby,
      the conditional log-likelihood is used for evaluation_runs.
    - Fits the model with the previously selected hyperparameter configuration

    Args:
      X: numpy array to be conditioned on - shape: (n_samples, n_dim_x)
      Y: numpy array of y targets - shape: (n_samples, n_dim_y)
      n_folds: number of cross-validation folds (positive integer)
      param_grid: (optional) a dictionary with the hyperparameters of the model as key and and a list of respective \
                  parametrizations as value. The hyperparameter search is performed over the cartesian product of \
                  the provided lists.

                  Example:
                  {"n_centers": [20, 50, 100, 200],
                   "center_sampling_method": ["agglomerative", "k_means", "random"],
                   "keep_edges": [True, False]
                  }

    """


    # save properties of data
    self.n_samples = X.shape[0]
    self.x_std = np.std(X, axis=0)
    self.y_std = np.std(Y, axis=0)

    if param_grid is None:
      param_grid = self._param_grid()

    cv_model = GridSearchCV(self, param_grid, fit_params=None, n_jobs=-1, refit=True, cv=n_folds,
                 verbose=1)
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")  # don't print division by zero warning
      cv_model.fit(X,Y)
    best_params = cv_model.best_params_
    print("Cross-Validation terminated")
    print("Best likelihood score: %.4f"%cv_model.best_score_)
    print("Best params:", best_params)
    self.set_params(**cv_model.best_params_)
    self.fit(X,Y)

  def get_params(self, deep=True):
    """ Get parameters for this estimator.

    Args:
      deep: boolean, optional If True, will return the parameters for this estimator and \
             contained subobjects that are estimators.

    Returns:
      params - mapping of string to any Parameter names mapped to their values.

    """
    param_dict = super(BaseDensityEstimator, self).get_params(deep=deep)
    param_dict['estimator'] = self.__class__.__name__

    for x in ["n_centers", "center_sampling_method", "x_noise_std", "y_noise_std",
              "random_seed", "ndim_x", "ndim_y"]:
      if hasattr(self, x):
        param_dict[x] = getattr(self, x)
      else:
        param_dict[x] = None

    return param_dict

  def plot(self, xlim=(0, 3.5), ylim=(0, 8), resolution=50):
    """ Plots the fitted conditional distribution if x and y are 1-dimensional each

    Args:
      xlim: 2-tuple specifying the x axis limits
      ylim: 2-tuple specifying the y axis limits
      resolution: integer specifying the resolution of plot
    """
    assert self.fitted, "model must be fitted to plot"
    assert self.ndim_x + self.ndim_y == 2, "Can only plot two dimensional distributions"

    # prepare mesh
    linspace_x = np.linspace(xlim[0], xlim[1], num=resolution)
    linspace_y = np.linspace(ylim[0], ylim[1], num=resolution)
    X, Y = np.meshgrid(linspace_x, linspace_y)
    X, Y = X.flatten(), Y.flatten()

    # calculate values of distribution
    Z = self.pdf(X, Y)

    X, Y, Z = X.reshape([resolution, resolution]), Y.reshape([resolution, resolution]), Z.reshape(
      [resolution, resolution])
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    surf = ax.plot_surface(X, Y, Z, cmap=cm.coolwarm, rcount=resolution, ccount=resolution,
                           linewidth=100, antialiased=True)
    plt.xlabel("x")
    plt.ylabel("y")
    plt.show()



  def __str__(self):
    raise NotImplementedError


class BaseMixtureEstimator(BaseDensityEstimator):

  def mean_(self, x_cond):
    """ Mean of the fitted distribution conditioned on x_cond
    Args:
      x_cond: different x values to condition on - numpy array of shape (n_values, ndim_x)

    Returns:
      Means E[y|x] corresponding to x_cond - numpy array of shape (n_values, ndim_y)
    """
    assert hasattr(self, '_get_mixture_components')
    assert self.fitted, "model must be fitted"

    means = np.zeros((x_cond.shape[0], self.ndim_y))
    weights, locs, _ = self._get_mixture_components(x_cond)
    assert weights.ndim == 2 and locs.ndim == 3
    for i in range(x_cond.shape[0]):
      # mean of density mixture is weights * means of density components
      means[i, :] = weights[i].dot(locs[i])
    return means

  def covariance(self, x_cond):
    """ Covariance of the fitted distribution conditioned on x_cond

      Args:
        x_cond: different x values to condition on - numpy array of shape (n_values, ndim_x)

      Returns:
        Covariances Cov[y|x] corresponding to x_cond - numpy array of shape (n_values, ndim_y, ndim_y)
    """
    assert self.fitted, "model must be fitted"
    covs = np.zeros((x_cond.shape[0], self.ndim_y, self.ndim_y))

    # compute global mean_of mixture model
    glob_mean = self.mean_(x_cond)

    weights, locs, scales = self._get_mixture_components(x_cond)

    for i in range(x_cond.shape[0]):
      c1 = np.diag(weights[i].dot(scales[i]))

      c2 = np.zeros(c1.shape)
      for j in range(weights.shape[0]):
        a = (locs[i][j] - glob_mean[i])
        d = weights[i][j] * np.outer(a,a)
        c2 += d
      covs[i] = c1 + c2

    return covs



  def cdf(self, X, Y):
    """ Predicts the conditional cumulative probability p(Y<=y|X=x). Requires the model to be fitted.

       Args:
         X: numpy array to be conditioned on - shape: (n_samples, n_dim_x)
         Y: numpy array of y targets - shape: (n_samples, n_dim_y)

       Returns:
         conditional cumulative probability p(Y<=y|X=x) - numpy array of shape (n_query_samples, )

    """
    assert self.fitted, "model must be fitted to compute likelihood score"
    assert hasattr(self, '_get_mixture_components'), "cdf computation requires _get_mixture_components method"

    X, Y = self._handle_input_dimensionality(X, Y, fitting=False)

    weights, locs, scales = self._get_mixture_components(X)

    P = np.zeros(X.shape[0])
    for i in range(X.shape[0]):
      for j in range(self.n_centers):
        P[i] += weights[i, j] * multivariate_normal.cdf(Y[i], mean=locs[i,j,:], cov=np.diag(scales[i,j,:]))
    return P