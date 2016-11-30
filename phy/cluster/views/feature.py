# -*- coding: utf-8 -*-

"""Feature view."""


# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------

import logging
import re

import numpy as np

from phy.utils import Bunch
from phy.utils._color import _colormap
from .base import ManualClusteringView

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Feature view
# -----------------------------------------------------------------------------

def _extend(channels, n=None):
    channels = list(channels)
    if n is None:
        return channels
    if not len(channels):  # pragma: no cover
        channels = [0]
    if len(channels) < n:
        channels.extend([channels[-1]] * (n - len(channels)))
    channels = channels[:n]
    assert len(channels) == n
    return channels


def _get_default_grid():
    """In the grid specification, 0 corresponds to the best channel, 1
    to the second best, and so on. A, B, C refer to the PC components."""
    s = """
    time,0A 1A,0A   0B,0A   1B,0A
    0A,1A   time,1A 0B,1A   1B,1A
    0A,0B   1A,0B   time,0B 1B,0B
    0A,1B   1A,1B   0B,1B   time,1B
    """.strip()
    dims = [[_ for _ in re.split(' +', line.strip())]
            for line in s.splitlines()]
    return dims


def _get_sym_lim(data):
    """Get symmetric data bounds."""
    m, M = data.min(), data.max()
    mm = max(abs(m), abs(M))
    return -mm, mm


def _get_point_color(clu_idx=None):
    if clu_idx is not None:
        color = tuple(_colormap(clu_idx)) + (.5,)
    else:
        color = (.5,) * 4
    assert len(color) == 4
    return color


def _get_point_size(clu_idx=None):
    return FeatureView._default_marker_size if clu_idx is not None else 1.


def _get_point_masks(masks=None, clu_idx=None):
    masks = masks if masks is not None else 1.
    # NOTE: we add the cluster relative index for the computation
    # of the depth on the GPU.
    return masks * .99999 + (clu_idx or 0)


def _get_masks_max(px, py):
    mx = px.get('masks', None)
    my = py.get('masks', None)
    if mx is None or my is None:
        return None
    return np.maximum(mx, my)


class FeatureView(ManualClusteringView):

    _default_marker_size = 5.
    default_shortcuts = {
        'increase': 'ctrl++',
        'decrease': 'ctrl+-',
        'toggle_automatic_channel_selection': 'c',
    }

    def __init__(self,
                 features=None,
                 attributes=None,
                 **kwargs):
        self._scaling = None

        assert features
        self.features = features

        self.n_cols = 4
        self.shape = (self.n_cols, self.n_cols)

        self.grid_dim = _get_default_grid()  # [i][j] = '..,..'

        # If this is True, the channels won't be automatically chosen
        # when new clusters are selected.
        self.fixed_channels = False

        # Channels being shown.
        self.channel_ids = None

        # Attributes: extra features. This is a dictionary
        # {name: array}
        # where each array is a `(n_spikes,)` array.
        self.attributes = attributes or {}

        # Initialize the view.
        super(FeatureView, self).__init__(layout='grid',
                                          shape=self.shape,
                                          enable_lasso=True,
                                          **kwargs)

    # Internal methods
    # -------------------------------------------------------------------------

    def _iter_subplots(self):
        """Yield (i, j, dim)."""
        for i in range(self.n_cols):
            for j in range(self.n_cols):
                # Skip lower-diagonal subplots.
                if i > j:
                    continue
                dim = self.grid_dim[i][j]
                dim_x, dim_y = dim.split(',')
                yield i, j, dim_x, dim_y

    def _get_axis_label(self, dim):
        """Return the channel id from a dimension, if applicable."""
        if dim[:-1].isdecimal():
            return str(self.channel_ids[int(dim[:-1])]) + dim[-1]
        else:
            return dim

    def _get_axis_data(self, bunch, dim, cluster_id=None):
        """Extract the points from the data on a given dimension.

        bunch is returned by the features() function.
        dim is the string specifying the dimensions to extract for the data.

        """
        if dim in self.attributes:
            return self.attributes[dim](cluster_id)
        masks = bunch.get('masks', None)
        assert dim not in self.attributes  # This is called only on PC data.
        s = 'ABCDEFGHIJ'
        # Channel relative index.
        c = int(dim[:-1])
        # Principal component: A=0, B=1, etc.
        d = s.index(dim[-1])
        if masks is not None:
            masks = masks[:, c]
        return Bunch(data=bunch.data[:, c, d],
                     masks=masks,
                     )

    def _get_axis_bounds(self, dim, bunch, values):
        """Return the min/max of an axis."""
        if dim in self.attributes:
            # Attribute: specified lim, or compute the min/max.
            vmin, vmax = bunch.get('lim', (None, None))
            if vmin is None:
                vmin = values.min()
            if vmax is None:
                vmax = values.max()
            return vmin, vmax
        # PC dimensions: use the common scaling.
        return (-1. / self.scaling, +1. / self.scaling)

    def _plot_points(self, i, j, dim_x, dim_y, bunch, clu_idx=None):
        cluster_id = self.cluster_ids[clu_idx] if clu_idx is not None else None
        px = self._get_axis_data(bunch, dim_x, cluster_id=cluster_id)
        py = self._get_axis_data(bunch, dim_y, cluster_id=cluster_id)
        xmin, xmax = self._get_axis_bounds(dim_x, bunch, px.data)
        ymin, ymax = self._get_axis_bounds(dim_y, bunch, py.data)
        masks = _get_masks_max(px, py)
        self[i, j].uscatter(x=px.data, y=py.data,
                            color=_get_point_color(clu_idx),
                            size=_get_point_size(clu_idx),
                            masks=_get_point_masks(clu_idx=clu_idx,
                                                   masks=masks),
                            data_bounds=(xmin, ymin, xmax, ymax),
                            )

    def _plot_labels(self):
        """Plot feature labels along left and bottom edge of subplots"""
        # iterate simultaneously over kth row in left column and
        # kth column in bottom row:
        br = self.n_cols - 1  # bottom row
        for k in range(0, self.n_cols):
            dim_x, _ = self.grid_dim[0][k].split(',')
            _, dim_y = self.grid_dim[k][br].split(',')
            # Get the channel ids corresponding to the relative channel indices
            # specified in the dimensions. Channel 0 corresponds to the first
            # best channel for the selected cluster, and so on.
            dim_x = self._get_axis_label(dim_x)
            dim_y = self._get_axis_label(dim_y)
            # Left edge of left column of subplots.
            self[k, 0].text(pos=[-1., 0.],
                            text=dim_y,
                            anchor=[-1.03, 0.],
                            data_bounds=None,
                            )
            # Bottom edge of bottom row of subplots.
            self[br, k].text(pos=[0., -1.],
                             text=dim_x,
                             anchor=[0., -1.04],
                             data_bounds=None,
                             )

    def _plot_axes(self):
        for i, j, dim_x, dim_y in self._iter_subplots():
            self[i, j].lines(pos=[[-1., 0., +1., 0.],
                                  [0., -1., 0., +1.]],
                             color=(.25, .25, .25, .5),
                             data_bounds=None,
                             )

    # Public methods
    # -------------------------------------------------------------------------

    def clear_channels(self):
        """Reset the dimensions."""
        self.channel_ids = None
        self.on_select()

    def on_select(self, cluster_ids=None):
        super(FeatureView, self).on_select(cluster_ids)
        cluster_ids = self.cluster_ids
        n_clusters = len(cluster_ids)
        if n_clusters == 0:
            return

        # Get the feature data.
        # Specify the channel ids if these are fixed, otherwise
        # choose the first cluster's best channels.
        c = self.channel_ids if self.fixed_channels else None
        bunchs = [self.features(cluster_id, channel_ids=c)
                  for cluster_id in cluster_ids]

        # Choose the channels based on the first selected cluster.
        channel_ids = list(bunchs[0].channel_ids)
        assert len(channel_ids)

        # Choose the channels automatically unless fixed_channels is set.
        if (not self.fixed_channels or self.channel_ids is None):
            self.channel_ids = channel_ids
        assert len(self.channel_ids)

        # Get the background data.
        background = self.features(channel_ids=self.channel_ids)

        # Plot all features.
        with self.building():
            self._plot_axes()

            # NOTE: the columns in bunch.data are ordered by decreasing quality
            # of the associated channels. The channels corresponding to each
            # column are given in bunch.channel_ids in the same order.

            # Find the initial scaling.
            if self._scaling in (None, np.inf):
                m = np.median(np.abs(background.data))
                if m < 1e-9:
                    m = 1.
                self._scaling = .1 / m

            for i, j, dim_x, dim_y in self._iter_subplots():
                # Plot the background points.
                self._plot_points(i, j, dim_x, dim_y, background)

                # Plot each cluster's data.
                for clu_idx, bunch in enumerate(bunchs):
                    self._plot_points(i, j, dim_x, dim_y, bunch,
                                      clu_idx=clu_idx)

            self._plot_labels()
            self.grid.add_boxes(self, self.shape)

    def attach(self, gui):
        """Attach the view to the GUI."""
        super(FeatureView, self).attach(gui)
        self.actions.add(self.increase)
        self.actions.add(self.decrease)
        self.actions.add(self.clear_channels)
        self.actions.add(self.toggle_automatic_channel_selection)

        gui.connect_(self.on_channel_click)
        gui.connect_(self.on_request_split)

    @property
    def state(self):
        return Bunch(scaling=self.scaling)

    def on_channel_click(self, channel_id=None, key=None, button=None):
        """Respond to the click on a channel."""
        channels = self.channel_ids
        if channels is None:
            return
        assert len(channels) >= 2
        # Get the axis from the pressed button (1, 2, etc.)
        # axis = 'x' if button == 1 else 'y'
        channels[0 if button == 1 else 1] = channel_id
        # Fix the channels temporarily.
        fc = self.fixed_channels
        self.fixed_channels = True
        self.on_select()
        self.fixed_channels = fc

    def on_request_split(self):
        """Return the spikes enclosed by the lasso."""
        if self.lasso.count < 3:  # pragma: no cover
            return []
        assert len(self.channel_ids)
        # TODO
        #
        # # Concatenate the points from all selected clusters.
        # assert isinstance(data, list)
        # pos = []
        # for d in data:
        #     i, j = self.lasso.box
        #
        #     pos.append(np.c_[x, y].astype(np.float64))
        # pos = np.vstack(pos)
        #
        # ind = self.lasso.in_polygon(pos)
        # self.lasso.clear()
        # return spike_ids[ind]
        return

    def toggle_automatic_channel_selection(self):
        """Toggle the automatic selection of channels when the cluster
        selection changes."""
        self.fixed_channels = not self.fixed_channels

    # Feature scaling
    # -------------------------------------------------------------------------

    @property
    def scaling(self):
        return self._scaling or 1.

    @scaling.setter
    def scaling(self, value):
        self._scaling = value

    def increase(self):
        """Increase the scaling of the features."""
        self.scaling *= 1.2
        self.on_select()

    def decrease(self):
        """Decrease the scaling of the features."""
        self.scaling /= 1.2
        self.on_select()
