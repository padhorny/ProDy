# ProDy: A Python Package for Protein Structural Dynamics Analysis
# 
# Copyright (C) 2010  Ahmet Bakan <ahb12@pitt.edu>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

"""This module defines a class for working on conformational ensembles and 
also arbitrary coordinate data sets.

Classes
-------

  * :class:`Ensemble`
  * :class:`Conformation`
  
Functions
---------

    * :func:`getSumOfWeights`

"""

__author__ = 'Ahmet Bakan'
__copyright__ = 'Copyright (C) 2010  Ahmet Bakan'


import os.path
import time

import numpy as np

from prody import ProDyLogger as LOGGER
from prody import measure

__all__ = ['Ensemble', 'Conformation', 'getSumOfWeights', 'showSumOfWeights']
        
class EnsembleError(Exception):
    pass

class Ensemble(object):
    
    """A class for ensemble analysis.
    
    Indexing returns a :class:`Conformation` instance, whereas slicing returns 
    an :class:`Ensemble` instance that contains subset of conformations.
    The ensemble obtained by slicing has the same reference coordinates.

    """

    def __init__(self, name):
        """Instantiate with a name."""
        self._name = str(name)
        self._ensemble = []
        self._confs = None       # coordinate data
        self._weights = None
        self._coords = None         # reference
        self._n_atoms = None
        self._transformations = []    # from last superimposition
        
    def __getitem__(self, index):
        """Return a conformation at given index."""
        if isinstance(index, int):
            return self._getConformation(index) 
        elif isinstance(index, slice):
            ens = Ensemble('{0:s} ({1[0]:d}:{1[1]:d}:{1[2]:d})'.format(
                                self._name, index.indices(len(self))))
            ens.setCoordinates(self.getCoordinates())
            ens.addCoordset(self._confs[index].copy())
            return ens
        else:
            raise IndexError('invalid index')
            
    def __len__(self):
        return len(self._ensemble)
        
    def __iter__(self):
        return self._ensemble.__iter__()
    
    def __repr__(self):
        return '<Ensemble: {0:s} ({1:d} conformations, {2:d} atoms)>'.format(
                                        self._name, len(self), self._n_atoms)

    def __str__(self):
        return 'Ensemble {0:s}'.format(self._name)

    def _getConformation(self, index):
        conf = self._ensemble[index]
        if conf is None:
            conf = Conformation(self, index, str(index))
            self._ensemble[index] = conf
        return conf
    
    def getName(self):
        """Return name of the conformation ensemble."""
        return self._name

    def setName(self, name):
        """Set name of the ensemble instance."""
        self._name = name
    
    def getNumOfAtoms(self):
        """Return number of atoms."""
        return self._n_atoms
    
    def getNumOfConfs(self):
        """Return number of conformations."""
        return len(self._ensemble)

    def getCoordinates(self):
        """Return reference coordinates of the ensemble."""
        return self._coords.copy()

    def setCoordinates(self, coords):
        """Set reference coordinates of the ensemble."""

        if not isinstance(coords, np.ndarray):
            try:
                coords = coords.getCoordinates()
            except AttributeError:
                raise TypeError('coords must be an ndarray instance or '
                                'must contain getCoordinates as an attribute')

        elif coords.ndim != 2:
            raise ValueError('coordinates must be a 2d array')
        elif coords.shape[1] != 3:
            raise ValueError('shape of coordinates must be (n_atoms,3)')
        elif coords.dtype != np.float64:
            try:
                coords.astype(np.float64)
            except ValueError:
                raise ValueError('coords array cannot be assigned type '
                                 '{0:s}'.format(np.float64))
        
        if self._n_atoms is not None:
            if coords.shape[0] != self._n_atoms:
                raise ValueError('shape of coords must be (n_atoms,3)')
        else:
            self._n_atoms = coords.shape[0]    
        self._coords = coords
        
   
    def addCoordset(self, coords, weights=None):
        """Add a NumPy array or coordinates from atoms as a conformation.
        
        AtomGroup, Chain, Residue, Selection, Atom, and AtomMap instances are 
        acceptable as *coords* argument.
        
        """
        ag = None
        if not isinstance(coords, np.ndarray):
            try:
                ag = coords
                coords = ag.getCoordinates()
            except AttributeError:
                raise TypeError('coords must be an ndarray instance or '
                                'must contain getCoordinates as an attribute')
            
        if not coords.ndim in (2, 3):
            raise ValueError('coords must be a 2d or a 3d array')
        elif coords.dtype != np.float64:
            try:
                coords.astype(np.float64)
            except ValueError:
                raise ValueError('coords array cannot be assigned type '
                                 '{0:s}'.format(np.float64))
        
        if self._n_atoms is None:
            self._n_atoms = coords.shape[-2]
        else:
            if coords.shape[-2] != self._n_atoms:
                raise ValueError('shape of conf must be (n_atoms,3)')
        n_atoms = self._n_atoms

        if coords.ndim == 2:
            coords = coords.reshape((1, self._n_atoms, 3))
        n_confs = coords.shape[0]
            
        
        if weights is not None:
            if not isinstance(weights, np.ndarray):
                raise TypeError('weights must be an ndarray')
            elif not weights.ndim in (1, 2, 3):
                raise ValueError('weights must be a 1d or a 2d array')
            elif weights.ndim in (2, 3) and weights.shape[-1] != 1:
                raise ValueError('shape of weights must be ([n_coordsets,] number_of_atoms, 1)')
            elif weights.dtype != np.float64:
                try:
                    weights.astype(np.float64)
                except ValueError:
                    raise ValueError('weights array cannot be assigned type '
                                     '{0:s}'.format(np.float64))
            if weights.ndim == 1:
                weights = weights.reshape((1, n_atoms, 1))
            
            if n_confs > 1:
                weights = np.tile(weights, (n_confs, n_atoms, 1))
            
            

        
        if self._confs is None: 
            self._confs = coords
            self._weights = weights
        else:
            self._confs = np.concatenate((self._confs, coords), axis=0)
            if weights is not None:
                self._weights = np.concatenate((self._weights, weights), axis=0)
            else:
                if self._weights is not None:
                    self._weights = np.concatenate((self._weights, 
                                        np.ones(n_confs, n_atoms, 1)), axis=0)
                
                
            
        if ag is None:
            self._ensemble += [None] * n_confs
            self._transformations += [None] * n_confs
        else:
            name = ag.getName()
            if ag.getNumOfCoordsets() > 0:
                name +=  ' ' + str(ag.getActiveCoordsetIndex())
            self._ensemble.append(Conformation(self, len(self._ensemble), name))
            self._transformations.append(None)
        

    def getCoordsets(self, indices=None):
        """Return a copy of coordinate sets at given indices.
        
        *indices* may be an integer, a list of integers or ``None``. ``None``
        returns all coordinate sets. 
    
        For reference coordinates, use getCoordinates method.
        
        """
        if indices is None:
            indices = slice(None)
        if self._confs is None:
            return None

        coords = self._confs[indices].copy()
        if self._weights is not None and self._weights.ndim == 3:
            for i, w in enumerate(self._weights[indices]):
                which = w.flatten()==0
                coords[i, which] = self._coords[which]
        return coords 

    
    def delCoordset(self, index):
        """Delete a coordinate set from the ensemble."""
        length = len(self._ensemble)
        which = np.ones(length, np.bool)
        which[index] = False
        if which.sum() == 0:
            self._confs = None
            self._weights = None
        else:
            self._confs = self._confs[which]
            if self._weights is not None:
                self._weights = self._weights[which]
            
        if isinstance(index, int):
            index = [index]
        else:
            index = list(index)
        index.sort(reverse=True)
        for i in index:
            conf = self._ensemble.pop(i)
            if conf is not None:
                conf._index = None
                conf._ensemble = None
            self._transformations.pop(i)
    
    def getNumOfCoordsets(self):
        """Return number of coordinate sets."""
        return len(self._ensemble)
    
    def iterCoordsets(self):
        """Iterate over coordinate sets by returning a copy of each coordinate set.
        
        Reference coordinates are not included.
        
        """
        for i in xrange(self._confs.shape[0]):
            yield self._confs[i].copy()
    
    def getWeights(self):
        if self._weights is None:
            return None
        else:
            return self._weights.copy()
    
    def getConformation(self, index):
        """Return conformation at given index."""
        return self._getConformation(index)
        
        
    def superimpose(self):
        """Superimpose the ensemble onto the reference coordinates."""
        if self._confs is None or len(self._confs) == 0: 
            raise AttributeError('conformations are not set')
        LOGGER.info('Superimposing structures.')
        start = time.time()
        self._superimpose()
        LOGGER.info(('Superimposition is completed in {0:.2f} '
                           'seconds.').format((time.time() - start)))
        
    def _superimpose(self):
        """Superimpose conformations and return new coordinates.
        
        This functions saves transformations in self._tranformations."""
        
        weights = self._weights
        coords = self._coords
        confs = self._confs
        transformations = self._transformations
        if weights is None:
            for i in xrange(len(self)):
                conf, t = measure.superimpose(confs[i], coords)
                confs[i] = conf
                transformations[i] = t
        else:         
            for i in xrange(len(self)):
                conf, t = measure.superimpose(confs[i], coords, weights[i])
                confs[i] = conf
                transformations[i] = t
        
    def transform(self):
        """Apply transformations from previous superimposition step.
        
        A potential use of this method is that superimposition may be performed
        by a core set of atoms. Then set coordinates may be used to select all
        atoms to apply the transformations calculated for the core atoms.
        
        """
        if self._transformations.count(None) > 0:
            raise EnsembleError('A transformation for each '
                                    'conformation is not calculated.')
        for i in range(self.conformations.shape[0]):
            self.conformations[i] = GF.transform(self.conformations[i], 
                                                 self._transformations[i][0],
                                                 self._transformations[i][1], 
                                                 self.weights[i])
    
    def iterimpose(self, rmsd=0.0001):
        """Iteratively superimpose the ensemble until convergence.
        
        Initially, all conformations are aligned with the reference 
        coordinates. Then mean coordinates are calculated, and are set
        as the new reference coordinates. This is repeated until 
        reference coordinates do not change. This is determined by
        the value of RMSD between the new and old reference coordinates.        
        
        :arg cutoff: RMSD (A) between old and new reference coordinates 
                     to converge
        :type cutoff: float, default is 0.0001
            
        """
        if self._confs is None or len(self._confs) == 0: 
            raise AttributeError('conformations are not set')
        LOGGER.info('Starting iterative superimposition')
        start = time.time()
        rmsdif = 1
        step = 0
        weights = self._weights
        if weights is not None:
            weightsum = weights.sum(axis=0)
        length = len(self)
        while rmsdif > rmsd:
            self._superimpose()
            if weights is None:
                newxyz = self._confs.sum(0) / length
            else:
                newxyz = (self._confs * weights).sum(0) / weightsum
            rmsdif = measure._getRMSD(self._coords, newxyz)
            self._coords = newxyz
            step += 1
            LOGGER.info(('Step #{0:d}: RMSD difference = '
                               '{1:.4e}').format(step, rmsdif))
        LOGGER.info('Iterative superimposition completed in {0:.2f}s.'
                    .format((time.time() - start)))
        
    def getMSF(self):
        """Calculate and return Mean-Square-Fluctuations."""
        if self.conformations is None: 
            return
        
        xyzmean = (self.conformations * 
                   self.weights).sum(0) / self.weights.sum(0)
        xyzdiff2 = np.power(self.conformations - xyzmean, 2).sum(2)
        weightsum = self.weights.sum(2)
        msf = (xyzdiff2 * weightsum).sum(0) / weightsum.sum(0)  
        return msf
            
    def getDeviations(self):
        """Return deviations from reference coordinates.
        
        """
        if not isinstance(self._confs, np.ndarray):
            LOGGER.warning('Conformations are not set.')
            return None
        if not isinstance(self._coords, np.ndarray):
            LOGGER.warning('Coordinates are not set.')
            return None
        
        return self.getCoordsets() - self._coords 
        
    def getRMSDs(self):
        """Calculate and return Root Mean Square Deviations."""
        if self._confs is None: 
            return None
        weights = self._weights
        if weights is None:
            wsum_axis_2 = 1
            wsum_axis_1 = 1
        else:
            wsum_axis_2 = weights.sum(2)
            wsum_axis_1 = wsum_axis_2.sum(1)
        rmsd = np.sqrt((np.power(self.getDeviations(), 2).sum(2) * 
                        wsum_axis_2).sum(1) / wsum_axis_1)
        return rmsd


class Conformation(object):

    """A class to provide methods on a conformation in a an ensemble.
    
    Instances of this class do not keep coordinate and weights data.
    
    
    """
    
    __slots__ = ['_ensemble', '_index', '_name']

    def __init__(self, ensemble, index, name):
        """Instantiate with an ensemble instance, index, and a name."""
        self._name = name
        self._ensemble = ensemble
        self._index = index
        
    def __repr__(self):
        return '<Conformation: {0:s} from {1:s} (index {2:d})>'.format(
                    self._name, self._ensemble._name, self._index)

    def getEnsemble(self):
        """Return the ensemble that this conformation belongs to."""
        return self._ensemble
    
    def getIndex(self):
        """Return the index of the conformation."""
        return self._index
    
    def getName(self):
        """Return name of the conformation instance."""
        return self._name
    
    def setName(self, name):
        """Set name of the conformation instance."""
        self._name = name

    def getCoordinates(self):
        """Return coordinate set for this conformation."""
        if self._ensemble._weights is None:
            return self._ensemble._confs[self._index].copy()
        else:
            coords = self._ensemble._confs[self._index].copy()
            weights = self._ensemble._weights[self._index].flatten()
            which = weights==0
            coords[which] = self._ensemble._coords[which]
            return coords 
    
    def getWeights(self):
        """Return coordinate weights, eg. occupancy or mass."""
        if self._ensemble._weights is None:
            return None
        else:
            return self._ensemble._weights[self._index].copy()

    def getDeviations(self):
        """Return deviations from the ensemble reference coordinates."""
        return self.getCoordinates() - self._ensemble._coords

    def getRMSD(self):
        """Return RMSD from the ensemble reference coordinates."""
        return measure._getRMSD(self._ensemble._coords,
                                 self._ensemble._confs[self._index], 
                                 self.getWeights())
    
    def getTransformation(self):
        """Return the transformation from the last superimposition."""
        return self._ensemble._transformations[self._index].copy()
    
def getSumOfWeights(ensemble):
    """Returns sum of weights from an ensemble.
    
    Weights are summed for each atom over conformations in the ensemble.
    Size of the plotted array will be equal to the number of atoms.
    
    When analyzing an ensemble of X-ray structures, this function can be used 
    to see how many times a residue is resolved.
    
    """
    
    if not isinstance(ensemble, prody.Ensemble):
        raise TypeError('ensemble must be an Ensemble instance')
    
    weights = ensemble.getWeights()
    
    if weights is None:
        return None
    
    return weights.sum(0)
    
    
def showSumOfWeights(ensemble, *args, **kwargs):
    """Show sum of weights from an ensemble using :func:`matplotlib.pyplot.plot`.
    
    Weights are summed for each atom over conformations in the ensemble.
    Size of the plotted array will be equal to the number of atoms.
    
    When analyzing an ensemble of X-ray structures, this function can be used 
    to see how many times a residue is resolved.
    """
    """
    *indices*, if given, will be used as X values. Otherwise, X axis will
    start from 0 and increase by 1 for each atom. 
    
    """
    if pl is None: prody.importPyPlot()
    if not isinstance(ensemble, prody.Ensemble):
        raise TypeError('ensemble must be an Ensemble instance')
    
    weights = getSumOfWeights(ensemble)
    
    if weights is None:
        return None
    
    show = pl.plot(weights, *args, **kwargs)
    
    axis = list(pl.axis())
    axis[2] = 0
    axis[3] += 1
    pl.axis(axis)
    pl.xlabel('Atom index')
    pl.ylabel('Sum of weights')
    return show
