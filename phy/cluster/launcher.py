# -*- coding: utf-8 -*-

"""Automatic clustering launcher."""

#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

from ..utils.array import PartialArray
from ..io.kwik.sparse_kk2 import sparsify_features_masks


#------------------------------------------------------------------------------
# Clustering class
#------------------------------------------------------------------------------

class KlustaKwik(object):
    """KlustaKwik automatic clustering algorithm."""
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self.__dict__.update(kwargs)

    def cluster(self, model=None, features=None,
                spike_ids=None, masks=None):
        # Get the features and masks.
        if model is not None:
            if features is None:
                features = PartialArray(model.features_masks, 0)
            if masks is None:
                masks = PartialArray(model.features_masks, 1)
        # Select some spikes if needed.
        if spike_ids is not None:
            features = features[spike_ids]
            masks = masks[spike_ids]
        # Convert the features and masks to the sparse structure used
        # by KlustaKwik2.
        data = sparsify_features_masks(features, masks)
        data = data.to_sparse_data()
        # Run KK2.
        from klustakwik2 import KK
        num_starting_clusters = self._kwargs.pop('num_starting_clusters')
        kk = KK(data, **self._kwargs)
        kk.cluster_mask_starts(num_starting_clusters)
        spike_clusters = kk.clusters
        return spike_clusters


def run(model, algorithm='klustakwik2', spike_ids=None, **kwargs):
    """Launch an automatic clustering algorithm on the model.

    Parameters
    ----------

    model : BaseModel
        A model.
    algorithm : str
        Only 'klustakwik2' is supported currently.
    **kwargs
        Parameters for KK2.

    """
    assert algorithm == 'klustakwik2'
    kk = KlustaKwik(**kwargs)
    return kk.cluster(model=model, spike_ids=spike_ids)
