#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec  7 04:37:00 2017

@author: scott
"""

import os, re
import numpy as np
import matplotlib as mpl
from matplotlib import pyplot as plt

calibration_0 = {'direct_beam_x': 	 277,
                 'direct_beam_y': 	 91,
                 'Sample_Detector_distance_pixels': 	4085.27,
                 'Sample_Detector_distance_mm':      702.666}


shape_0 = (195, 487)

def read_RAW(file, shape=shape_0):

    '''
    Copied from Pilatus_Calibrate.py, by Kevin Stone, SSRL
    '''
    print("Reading RAW file here...")

    if True:
    #try:    # I want to see what error it gives when there's an error.
        with open(file, 'rb') as im:
            arr = np.fromstring(im.read(), dtype='int32')
        arr.shape = shape
        arr = np.fliplr(arr)  #for the way mounted at BL2-1
        return arr

    #except:
    #    print("Error reading file: %s" % file)
    #    return None

def read_calibration(file):
    calibration = {}
    with open(file) as cal:
        lines = cal.readlines()
    for line in lines:
        key, value = line.split()
        calibration[key] = value
#    db_pixel = [487-db_x, db_y]  #This line is important for the way the detector is mounted at BL2-1
    return calibration     
  

class Pilatus:
    def __init__(self, file, shape=shape_0, 
                 calibration=calibration_0, alpha=None, tth=None,
                 xslits=None,  yslits=[60, 430]):
        
        print('loading Pilatus object for ' + file)
        directory, name = os.path.split(file)
        self.shape = shape
        self.directory = directory
        self.name = name
        self.im = read_RAW(file, shape=shape)
        if type(calibration) is str: #then it's a file
            calibration = read_calibration(calibration)
        self.calibration = calibration
        self.db_pixel = (calibration['direct_beam_y'],  #First dimension is in 
                         calibration['direct_beam_x'])  #Second dimension is in tth direction
                         #shape[1] -calibration['direct_beam_x']) 
                         #subtracted from shape[1] corresponding to the fliplr in read_RAW above
                         #The Cu(111) peak ligns up without this.
                         
                         
                         
                         #db_pixel needs to be a tuple to be read as a 2-d index to e.g. im
        #strangely, shape[1] is for dimension x. I still don't get numpy...
        self.R = calibration['Sample_Detector_distance_mm'] * 1e-3 
        # distance from sample to detector / m
        self.R_pixels = calibration['Sample_Detector_distance_pixels']
        self.dx = self.R/self.R_pixels #distance between pixels / m
        self.dy = self.R/self.R_pixels #disttance between pixels / m
        self.alpha = alpha  # sample angle wrt direct beam / deg
        self.tth = tth      # detector angle wrt direct beam / deg
        self.xslits = xslits
        self.yslits = yslits
        self.xs = self.dx * (np.arange(shape[0]) - self.db_pixel[0])
        self.ys = self.dy * (np.arange(shape[1]) - self.db_pixel[1])
    
    def apply_slits(self, xslits=None, yslits=None):
        if xslits is not None:
            self.xslits = xslits
        else:
            xslits = self.xslits
        if yslits is not None:
            self.yslits = yslits
        else:
            yslits = self.yslits
        im1 = self.im
        xs1 = self.xs
        ys1 = self.ys
        if xslits is not None:
            im1 = im1[xslits[0]:xslits[-1], :]
            xs1 = xs1[xslits[0]:xslits[-1]]
        if yslits is not None:
            im1 = im1[:, yslits[0]:yslits[-1]]
            ys1 = ys1[yslits[0]:yslits[-1]]   
        self.im1 = im1
        self.xs1 = xs1
        self.ys1 = ys1
        inslits = np.tile(True, self.shape)
        if xslits is not None:
            inslits[:xslits[0], :] = False
            inslits[xslits[1]:, :] = False
        if yslits is not None:
            inslits[:, :yslits[0]] = False
            inslits[:, yslits[1]:] = False
        self.inslits = inslits
        
    def show_image(self, aspect='auto', colormap='inferno', ax='new', 
                  norm=None, slits=True):
        #im = images[n]
        
        if slits:
            if 'im1' not in dir(self):
                self.apply_slits()
            im = self.im1
            xs = self.xs1  # first dimension is in phi direction
            ys = self.ys1  # second dimension is in tth direction
        else:
            im = self.im
            xs = self.xs  # first dimension is in phi direction
            ys = self.ys # second dimension is in tth direction
        # imshow makes the second dimension horizontal. I don't know why.            
        if type(norm) in [list, tuple]:
            norm = mpl.colors.Normalize(norm[0], norm[-1])
        if ax == 'new':
            fig, ax = plt.subplots()
        ax.imshow(im, extent=[ys[0]*1e3, ys[-1]*1e3, xs[0]*1e3, xs[-1]*1e3],
                 aspect=aspect, origin='lower', norm=norm,
                 cmap = colormap)    
        ax.set_xlabel('position / mm')
        ax.set_ylabel('position / mm')
        if 'tth' in dir(self):
            ax.set_title('centered at tth = ' + str(self.tth))
        return ax
    
    def get_map_xyz(self, override=False):
        '''
        Get local cartesian coordinates for each pixel on detector
        generates self.shape[0] x self.shape[1] x 3 array called map_xyz,
        such that map_xyz(i, j) is the location of pixel (i, j) on the 
        detector's coordinate system. Illustration below, in comment to 
        function get_map_sphere. The sample is at the origin in this local
        coordinate system, but the db_pixel is always on the z axis.
        map_xyz is saved as self.map_xyz and returned.
        If self.map_xyz is already there, it's only recalculated if override=True
        '''
        if 'map_xyz' in dir(self) and not override:
            return self.map_xyz
        
        shape = self.shape
        xs = self.xs
        ys = self.ys
        R = self.R
        
        map_x = np.transpose(np.tile(xs, [shape[1], 1]))
        map_y = np.tile(ys, [shape[0], 1])
        map_z = R * np.tile(1, shape)
        #print('shape(map_x), shape(map_y), shape(map_z) = ' 
        #      + str(np.shape(map_x)), ', ' + str(np.shape(map_y)) + 
        #      ', ' + str(np.shape(map_z)))
        
        map_xyz = np.stack([map_x, map_y, map_z], axis=-1)
        #now, map_xyz[i, j] = [x, y, z] for pixel [i, j] on the detector
        
        self.map_xyz = map_xyz
        return map_xyz
    
    def get_map_xyz_prime(self, tth=None, override=False):
        ''' 
        This function transforms the local coordinates of the detector (x,y,z) 
        to absolute coordinates (x,y,z)', in which the sample is at the origin 
        and the direct beam comes from the -z direction.
                Illustration below, in comment to get_map_sphere function.
        The resulting self.shape[0] x self.shape[1] x 3 arrahe is saved as 
        self.map_xyz_prime and returned.
        self.tth can be changed by inputting a new tth here,in which case
        map_xyz_prime is recalculated even if there is a self.map_xyz_prime.
        override=True forces both maps to be recalculated        
        Also, Einstein summation is beautiful. Super fast. No loop here!
        '''
        if tth is not None:
            self.tth = tth
        if 'map_xyz_prime' in dir(self) and tth is None and not override:
            return self.map_xyz_prime
        if 'map_xyz' not in dir(self):
            self.get_map_xyz(override=override)
        map_xyz = self.map_xyz

        TTH = self.tth * np.pi/180.0 #TwoTheta in radians
        rot_op = np.array([[1.0, 0.0, 0.0], 
                           [0.0, np.cos(TTH), np.sin(TTH)], 
                           [0.0, -1.0*np.sin(TTH), np.cos(TTH)]])
        
        map_xyz_prime = np.einsum('ij,...j', rot_op, map_xyz)  
        #Einstein sum. This is beautiful.
        #multiplies the matrix by the vector length 3 for each point.
        
        self.map_xyz_prime = map_xyz_prime
        return map_xyz_prime
    
    def get_map_sphere(self, tth=None, override=False):
        '''           
     z' ^       (i,j)       Illustrated: transformation of cartesian to spherical coordinates 
        |       __-*-_  y   At tth=0, the detector is in the z' direction from the sample
        | tth__/  |:  ->    At tth=90 deg, the detector is in the y' direction from the sample
        | __/   x v:        local (x, y) directions correspond to (phi, tth) directons at db pixel
        .----------:--> y'  Standard spherical coordinates transformed from (x,y,z)' 
         \'~.. phi :        [such that first coordinate is distance from sample to pixel (i,j)
          \   '~~..!        first angle (second coordinate) is between z' axis and pixel (i,j)
           \                and second angle (last coordinate) is between x' axis an   d 
         x' v               projection of pixel onto (x,y)' plane]
        
        Spherical coordinates in terms of XRD angle convenction are thus (r, tth, pi/2-phi)
        This function creates self.map_sphere containing (r, tth, pi/2-phi) coordinates for
        each detector pixel (i,j). This self.shape[0] x self.shape[1] x 3 matrix
        is saved as self.map_sphere and returned.
        if tth is input, self.tth is changed, and get_map_xyz_prime recalculated.
        override=True causes the calculation of all coordinate maps to be done afresh.
        Super fast, no loop! 
        ''' 
        if 'map_xyz_prime' not in dir(self) or tth is not None or override:
            self.get_map_xyz_prime(tth=tth, override=override)
        map_xyz_prime = self.map_xyz_prime
        map_x_p = map_xyz_prime[:,:,0]
        map_y_p = map_xyz_prime[:,:,1]
        map_z_p = map_xyz_prime[:,:,2]
        map_r = np.sqrt(map_x_p**2 + map_y_p**2 + map_z_p**2)
        map_tth = np.arccos(map_z_p/map_r) * 180/np.pi   # in degrees
        map_phi = np.arcsin(map_x_p/(np.sqrt(map_x_p**2 + map_y_p**2))) * 180/np.pi # in degrees
        map_sphere = np.stack([map_r, map_tth, 90-map_phi], axis=-1)
        self.map_sphere = map_sphere
        self.map_tth = map_tth
        self.map_phi = map_phi
        self.map_r = map_r
        return map_sphere
    
    def get_map_tth(self, tth=None, override=False):
        '''
        same as get_map_sphere but only returns tthss. Saves a bit of time
        '''
        if 'map_xyz_prime' not in dir(self) or tth is not None or override:
            self.get_map_xyz_prime(tth=tth, override=override)
        map_xyz_prime = self.map_xyz_prime
        map_x_p = map_xyz_prime[:,:,0]
        map_y_p = map_xyz_prime[:,:,1]
        map_z_p = map_xyz_prime[:,:,2]
        map_r = np.sqrt(map_x_p**2 + map_y_p**2 + map_z_p**2)
        map_tth = np.arccos(map_z_p/map_r) * 180/np.pi   # in degrees
        self.map_tth = map_tth
        return map_tth
        
    def tth_spectrum(self, stepsize=0.05, tth=None, override=False,
                     slits=True, xslits=None, yslits=None,
                     out='spectrum', 
                     method='average', min_pixels=10):
        '''
        Returns, as specified by argument 'out', either
            bins: a dictionary where key is the number n, counting from zero, 
                of the nth tth interval with width stepsize, for each such 
                interval catching pixels in the image; and value is the sum of
                the value at each pixel 
            spectrum: tth and counts as 1d arrays. tth is at the center of the
                interval
            
        '''
        if not override and tth is None \
        and 'stepsize' in dir(self) and 'method' in dir(self):
            if out=='bins' and 'bins' in dir(self) \
            and self.stepsize==stepsize and self.method==method:
                return self.bins
            elif out=='spectrum' and 'spectrum' in dir(self) \
            and self.stepsize==stepsize and self.method==method:
                return self.spectrum
        print('calculating spectrum for ' + self.name)
        self.method = method
        self.stepsize = stepsize
        
        if slits:
            self.apply_slits(xslits=xslits, yslits=yslits)

        if 'map_tth' not in dir(self) or tth is not None or override:
            self.get_map_tth(tth=tth, override=override)
        map_tth = self.map_tth
        
        map_bin = np.floor(map_tth/stepsize)  
        #This does the same as np.digitize does, but without having to define the bins first
        self.map_bin = map_bin
        
        #bins = {'stepsize':stepsize, 'method':method} # It's nicer to only have integer keys
        bins = {}
        tth_vec = []
        counts_vec = []
        for step in range(int(np.min(map_bin)), int(np.max(map_bin)+1)):
            inbin = map_bin == step
            if slits:
                inbin = np.logical_and(inbin, self.inslits)
           # print([(i,j) for i in xrange for j in yrange if inbin[i,j]])

            pixel_counts = self.im[inbin][:]
            if method == 'sum':
                counts = sum(pixel_counts)
            if method == 'average':
                if len(pixel_counts)<min_pixels:
                    continue
                counts = np.mean(pixel_counts)
            bins[step] = counts
            tth_vec += [(step + 1/2) * stepsize]
            counts_vec += [counts]
        
        spectrum = (np.array(tth_vec), np.array(counts_vec))
        self.bins = bins
        self.spectrum = spectrum

        if out == 'spectrum':
            return spectrum
        elif out == 'bins':
            return bins
    
    def plot_spectrum(self, ax='new', specs={}, *args, **kwargs):
        kwargs.update(out='spectrum')
        tth_vec, counts_vec = self.tth_spectrum(*args, **kwargs)
        if ax == 'new':
            fig, ax = plt.subplots()
        ax.plot(tth_vec, counts_vec, **specs)
        ax.set_xlabel('tth / deg')
        if self.method == 'sum':
            ax.set_ylabel('counts')
        elif self.method == 'average':
            ax.set_ylabel('counts per pixel')
        return ax
    
    
    