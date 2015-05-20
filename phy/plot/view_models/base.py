# -*- coding: utf-8 -*-

"""Base view model."""

#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import numpy as np

from ...utils import _as_list
from ...utils.array import _unique, _spikes_in_clusters
from ...utils.selector import Selector


#------------------------------------------------------------------------------
# Misc
#------------------------------------------------------------------------------

# Default color map for the selected clusters.
_COLORMAP = np.array([[102, 194, 165],
                      [252, 141, 98],
                      [141, 160, 203],
                      [231, 138, 195],
                      [166, 216, 84],
                      [255, 217, 47],
                      [229, 196, 148],
                      ])


def _create_view(cls, backend=None, **kwargs):
    if backend in ('pyqt4', None):
        kwargs.update({'always_on_top': True})
    return cls(**kwargs)


def _selected_clusters_colors(n_clusters):
    if n_clusters > _COLORMAP.shape[0]:
        colors = np.tile(_COLORMAP, (1 + n_clusters // _COLORMAP.shape[0], 1))
    else:
        colors = _COLORMAP
    return colors[:n_clusters, ...] / 255.


#------------------------------------------------------------------------------
# BaseViewModel
#------------------------------------------------------------------------------

class BaseViewModel(object):
    """Create a view from a model."""
    _view_class = None
    _view_name = ''
    _imported_params = ('position', 'size',)
    scale_factor = 1.

    def __init__(self, model=None, store=None,
                 n_spikes_max=None, excerpt_size=None,
                 position=None, size=None, backend=None,
                 cluster_ids=None,
                 **kwargs):

        self._model = model
        self._store = store
        if cluster_ids is not None:
            cluster_ids = _as_list(cluster_ids)

        # Create the spike/cluster selector.
        self._selector = Selector(model.spike_clusters,
                                  n_spikes_max=n_spikes_max,
                                  excerpt_size=excerpt_size,
                                  )

        # Create the VisPy canvas.
        self._view = _create_view(self._view_class,
                                  backend=backend,
                                  position=position or (200, 200),
                                  size=size or (600, 600),
                                  )

        # Set passed keyword arguments as attributes.
        for key, value in kwargs.items():
            setattr(self, key, value)

        @self._view.connect
        def on_draw(event):
            if self._view.visual.empty:
                self.on_open()
                if cluster_ids:
                    self.select(cluster_ids)

    @property
    def model(self):
        return self._model

    @property
    def name(self):
        return self._view_name

    @property
    def store(self):
        return self._store

    @property
    def selector(self):
        return self._selector

    @property
    def view(self):
        return self._view

    @property
    def cluster_ids(self):
        """Selected clusters."""
        return self._selector.selected_clusters

    @property
    def spike_ids(self):
        """Selected spikes."""
        return self._selector.selected_spikes

    @property
    def n_clusters(self):
        """Number of selected clusters."""
        return self._selector.n_clusters

    @property
    def n_spikes(self):
        """Number of selected spikes."""
        return self._selector.n_spikes

    def load(self, name, spike_selection=None):
        """Load data from the store or the model.

        By default, the data for the selected spikes is loaded.
        Load the data from all spikes in the selected clusters with
        `spike_selection='all'`.

        """
        spikes = self.spike_ids if spike_selection is None else None
        if self._store is not None and len(self.cluster_ids):
            return self._store.load(name, self.cluster_ids, spikes=spikes)
        else:
            out = getattr(self._model, name)
            if spikes is None:
                spikes = _spikes_in_clusters(self.model.spike_clusters,
                                             self.cluster_ids)
            if len(spikes) == 0:
                return np.zeros((0,) + out.shape[1:], dtype=out.dtype)
            else:
                return out[spikes]

    def _update_spike_clusters(self, spikes=None):
        """Update the spike clusters and cluster colors."""
        if spikes is None:
            spikes = self.spike_ids
        spike_clusters = self.model.spike_clusters[spikes]
        n_clusters = len(_unique(spike_clusters))
        visual = self._view.visual
        # This updates the list of unique clusters in the view.
        visual.spike_clusters = spike_clusters
        visual.cluster_colors = _selected_clusters_colors(n_clusters)

    def on_open(self):
        """Initialize the view after the model has been loaded.

        May be overriden."""

    def select(self, cluster_ids):
        """Select a set of clusters."""
        self._selector.selected_clusters = cluster_ids
        self.on_select()

    def on_select(self):
        """Update the view after a new selection has been made.

        Must be overriden."""
        self._update_spike_clusters()
        self._view.update()

    def on_close(self):
        """Clear the view when the model is closed."""
        self._view.visual.spike_clusters = []
        self._view.update()

    def exported_params(self, save_size_pos=True):
        """Return a dictionary of variables to save when the view is closed."""
        if save_size_pos:
            return {
                'position': self._view.position,
                'size': self._view.size,
            }
        else:
            return {}

    def show(self):
        """Show the view."""
        self._view.show()