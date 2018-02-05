"""
Module that contains solvers for solving systems in AMfe.
"""

#IDEAS:
#
# First define options for Solver
#   options1 = {'beta': 0.5, 'gamma': 0.3}
#   options2 = {'rho': 0.9, 'beta': 0.5}
#
# Second instantiate Solver instances
#   solver1 = NonlinearGeneralizedAlphaSolver(options1)
#   solver2 = LinearGeneralizedAlphaSolver(options2)
#
# Third call the solve method and pass a system to solve
#   mysys = amfe.MechanicalSystem()
#   solver1.solve(mysys)
#   solver2.solve(mysys)
#
#
# Optional: Generate Shortcut for MechanicalSystem-class mysys.solve(solver1)
#
# The first way is advantageous: Example:
# Solve Method of Solver class:
#   def solve(mechanical_system):
#       if type(mechanical_system)== 'ConstrainedSystem':
#           raise ValueError('This kind of system cannot be solved by this solver, use ConstrainedSolver for ConstrainedSystems instead')
#       K = mechanical_system.K
#       res = ...
#       solver.solve(self)
#

import numpy as np
import scipy as sp
import time

from .mechanical_system import *
from .linalg import *

__all__ = ['choose_solver',
           'Solver',
           'NonlinearStaticsSolver',
           'LinearStaticsSolver',
           'NonlinearDynamicsSolver',
           'LinearDynamicsSolver',
           'GeneralizedAlphaNonlinearDynamicsSolver',
           'JWHAlphaNonlinearDynamicsSolver',
           'GeneralizedAlphaLinearDynamicsSolver',
           'JWHAlphaLinearDynamicsSolver',
           'ConstraintSystemSolver']


abort_statement = '''
###############################################################################
#### The current computation has been aborted. No convergence was gained
#### within the number of given iteration steps.
###############################################################################
'''


# Most general solver class
# --------------------
class Solver:
    '''
    Most general solver class for the mechanical system.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver.
    '''

    def __init__(self, mechanical_system, **options):
        self.mechanical_system = mechanical_system

        # read options
        if 'linsolver' in options:
            self.linsolver = options['linsolver']
        else:
            self.linsolver = PardisoSolver

        if 'linsolveroptions' in options:
            self.linsolveroptions = options['linsolveroptions']
        return

    def solve(self):
        pass


# Solver classes for all statics solver
# -------------------------------------------
class NonlinearStaticsSolver(Solver):
    '''
    Class for solving the nonlinear static problem of the mechanical system.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, **options)

        # read options
        if 'no_of_load_steps' in options:
            self.no_of_load_steps = options['no_of_load_steps']
        else:
            self.no_of_load_steps = 10

        if 'rtol' in options:
            self.rtol = options['rtol']
        else:
            self.rtol = 1.0E-9

        if 'atol' in options:
            self.atol = options['atol']
        else:
            self.atol = 1.0E-6

        if 'newton_damping' in options:
            self.newton_damping = options['newton_damping']
        else:
            self.newton_damping = 1.0

        if 'n_max_iter' in options:
            self.n_max_iter = options['n_max_iter']
        else:
            self.n_max_iter = 1000

        if 'smplfd_nwtn_itr' in options:
            self.smplfd_nwtn_itr = options['smplfd_nwtn_itr']
        else:
            self.smplfd_nwtn_itr = 1

        if 'verbose' in options:
            self.verbose = options['verbose']
        else:
            self.verbose = False

        if 'track_niter' in options:
            self.track_niter = options['track_niter']
        else:
            self.track_niter = False

        if 'write_iter' in options:
            self.write_iter = options['write_iter']
        else:
            self.write_iter = False

        if 'conv_abort' in options:
            self.conv_abort = options['conv_abort']
        else:
            self.conv_abort = True

        if 'save' in options:
            self.save = options['save']
        else:
            self.save = True
        return

    def solve(self):
        '''
        Solves the nonlinear static problem of the mechanical system.
            
        Parameters
        ----------


        Returns
        -------
        u_output : ndarray, shape(ndim, no_of_load_steps)
            Static displacement field (solution); q[:,-1] is the final (last) displacement.
        '''
        # start time measurement
        t_clock_start = time.time()

        # initialize variables and set parameters
        self.mechanical_system.clear_timesteps()
        iteration_info = []
        u_output = []
        stepwidth = 1/self.no_of_load_steps
        K, f_int = self.mechanical_system.K_and_f()
        ndof = K.shape[0]
        u = np.zeros(ndof)
        du = np.zeros(ndof)

        # write initial state
        self.mechanical_system.write_timestep(0.0, u)

        # load step loop
        for t in np.arange(stepwidth, 1.0 + stepwidth, stepwidth):

            K, f_int= self.mechanical_system.K_and_f(u, t)
            f_ext = self.mechanical_system.f_ext(u, du, t)
            res = -f_int + f_ext
            abs_res = norm_of_vector(res)
            abs_f_ext = norm_of_vector(f_ext)

            # Newton iteration loop
            n_iter = 0
            while (abs_res > self.rtol*abs_f_ext + self.atol) and (self.n_max_iter > n_iter):

                # solve for correction
                self.linsolver.set_A(K)
                delta_u = self.linsolver.solve(res)

                # correct displacement
                u += delta_u*self.newton_damping
                if (n_iter % self.smplfd_nwtn_itr) is 0:
                    K, f_int = self.mechanical_system.K_and_f(u, t)
                    f_ext = self.mechanical_system.f_ext(u, du, t)
                res = -f_int + f_ext
                abs_f_ext = norm_of_vector(f_ext)
                abs_res = norm_of_vector(res)
                n_iter += 1

                if self.verbose:
                    print('Step: {0:3d}, iteration#: {1:3d}, residual: {2:6.3E}'.format(int(t), n_iter, abs_res))

                if self.write_iter:
                    self.mechanical_system.write_timestep(t + n_iter*0.000001, u)

                # exit, if max iterations exceeded
                if (n_iter >= self.n_max_iter) and self.conv_abort:
                    u_output = np.array(u_output).T
                    print(abort_statement)
                    t_clock_end = time.time()
                    print('Time for static solution: {0:6.3f} seconds'.format(t_clock_end - t_clock_start))
                    return u_output

            # end of Newton iteration loop

            if self.save:
                self.mechanical_system.write_timestep(t, u)
            u_output.append(u.copy())

            if self.track_niter:
                iteration_info.append((t, n_iter, abs_res))

        # end of load step loop

        self.iteration_info = np.array(iteration_info)
        u_output = np.array(u_output).T
        t_clock_end = time.time()
        print('Time for solving nonlinear displacements: {0:6.3f} seconds'.format(t_clock_end - t_clock_start))
        return u_output


class LinearStaticsSolver(Solver):
    '''
    Class for solving the linear static problem of the mechanical system linearized around zero-displacement.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be linearized at zero displacement and solved.
    options : Dictionary
        Options for solver.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, options)

        # read options
        if 't' in options:
            self.t = options['t']
        else:
            self.t = 1.0
        return

    def solve(self):
        '''
        Solves the linear static problem of the mechanical system linearized around 
        zero-displacement.

        Parameters
        ----------


        Returns
        -------
        u : ndaray
            Static displacement field (solution).
        '''

        # prepare mechanical_system
        self.mechanical_system.clear_timesteps()

        print('Assembling external force and stiffness...')
        K = self.mechanical_system.K(u=None, t=self.t)
        f_ext = self.mechanical_system.f_ext(u=None, du=None, t=self.t)
        self.mechanical_system.write_timestep(0.0, 0.0*f_ext)  # write initial state

        print('Start solving linear static problem...')
        self.linsolver.set_A(K)
        u = self.linsolver.solve(f_ext)
        self.mechanical_system.write_timestep(self.t, u)  # write deformed state
        print('Static problem solved.')
        return u


# General solver class for all dynamics solver
# --------------------------------------------
class NonlinearDynamicsSolver(Solver):
    '''
    General class for solving the nonlinear dynamic problem of the mechanical system.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver:
        initial_conditions : dict {'q0': numpy.array, 'dq0': numpy.array}
            Initial conditions/displacement and velocity for solver.
        t0 : float
            Initial time.
        t_end : float
            End time.
        dt : float
            Time step size for time integration.
        dt_output : float
            Time step size for output.
        rtol : float

        atol : float

        n_iter_max : int

        conv_abort : Boolean

        verbose : Boolean
            If true, show some more information in command line.
        write_iter : Boolean
            If true, write iteration steps.
        track_niter : Boolean

        use_v : Boolean
            If true, time integration scheme needs additional variable v.


    References
    ----------
       [1]  M. Géradin and D.J. Rixen (2015): Mechanical vibrations. Theory and 
            application to structural dynamics. ISBN 978-1-118-90020-8.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, **options)

        # read options
        self.options = dict(**options)

        self.initial_conditions = self.set_initial_conditions(**options)

        if 't0' in options:
            self.t0 = options['t0']
        else:
            print('Attention: No initial time was given for time-integration, setting t0 = 0.0.')
            self.t0 = 0.0

        if 't_end' in options:
            self.t_end = options['t_end']
        else:
            print('Attention: No end time was given for time-integration, setting t_end = 1.0.')
            self.t_end = 1.0

        if 'dt' in options:
            self.dt = options['dt']
        else:
            raise ValueError('Error: No time step size was given for the time integration.')

        if 'dt_output' in options:
            self.dt_output = options['dt_output']
        else:
            self.dt_output = self.dt

        if 'rtol' in options:
            self.rtol = options['rtol']
        else:
            self.rtol = 1.0E-9

        if 'atol' in options:
            self.atol = options['atol']
        else:
            self.atol = 1.0E-6

        if 'n_iter_max' in options:
            self.n_iter_max = options['n_iter_max']
        else:
            self.n_iter_max = 30

        if 'conv_abort' in options:
            self.conv_abort = options['conv_abort']
        else:
            self.conv_abort = True

        if 'verbose' in options:
            self.verbose = options['verbose']
        else:
            self.verbose = False

        if 'write_iter' in options:
            self.write_iter = options['write_iter']
        else:
            self.write_iter = False

        if 'track_niter' in options:
            self.track_niter = options['track_niter']
        else:
            self.track_niter = False

        if 'use_v' in options:
            self.use_v = options['use_v']
        else:
            self.use_v = False
        return

    def set_initial_conditions(self, **options):
        if ('initial_conditions' in options) and ('q0' in options['initial_conditions']):
            q0 = options['initial_conditions']['q0']
            if len(q0) != self.mechanical_system.no_of_dofs:
                raise ValueError('Error: Dimension of q0 not valid for mechanical system.')
        else:
            print('Attention: No input for initial displacement is given, setting q0 = 0.')
            q0 = np.zeros(self.mechanical_system.no_of_dofs)

        if ('initial_conditions' in options) and ('dq0' in options['initial_conditions']):
            dq0 = options['initial_conditions']['dq0']
            if len(dq0) != self.mechanical_system.no_of_dofs:
                raise ValueError('Error: Dimension of dq0 is not valid for mechanical system.')
        else:
            print('Attention: No input for initial velocity is given, setting dq0 = 0.')
            dq0 = np.zeros(self.mechanical_system.no_of_dofs)
        return {'q0':q0, 'dq0':dq0}

    def set_parameters(self, **options):
        pass

    def predict(self, q, dq, v, ddq):
        pass

    def newton_raphson(self, q, dq, v, ddq, t, q_old, dq_old, v_old, ddq_old, t_old):
        pass

    def correct(self, q, dq, v, ddq, delta_q):
        pass

    def solve(self):
        '''
        Solves the nonlinear dynamic problem of the mechanical system.
    
        Parameters
        ----------

        '''


        # start time measurement
        t_clock_start = time.time()

        # initialize variables and set parameters
        self.mechanical_system.clear_timesteps()
        self.iteration_info = []
        t = self.t0
        dt = self.dt
        time_range = np.arange(self.t0, self.t_end, self.dt_output)
        q = self.initial_conditions['q0'].copy()
        dq = self.initial_conditions['dq0'].copy()
        if self.use_v:
            v = self.initial_conditions['dq0'].copy()
        else:
            v = np.empty((0, 0))
        ddq = np.zeros_like(q)
        f_ext = np.zeros_like(q)
        abs_f_ext = self.atol
        time_index = 0
        eps = 1E-13
        self.set_parameters(**self.options)

        # time step loop
        while time_index < len(time_range):
    
            # write output
            if t + eps >= time_range[time_index]:
                self.mechanical_system.write_timestep(t, q.copy())
                time_index += 1
                if time_index == len(time_range):
                    break

            # save old variables
            q_old = q.copy()
            dq_old = dq.copy()
            v_old = v.copy()
            ddq_old = ddq.copy()
            f_ext_old = f_ext.copy()
            t_old = t

            # predict new variables
            t += dt
            self.predict(q, dq, v, ddq)

            Jac, res, f_ext = self.newton_raphson(q, dq, v, ddq, t, q_old, dq_old, v_old, ddq_old, t_old)
            abs_f_ext = max(abs_f_ext, norm_of_vector(f_ext))
            res_abs = norm_of_vector(res)

            # Newton-Raphson iteration loop
            n_iter = 0
            while res_abs > self.rtol*abs_f_ext + self.atol:

                # solve for correction
                self.linsolver.set_A(Jac)
                delta_q = -self.linsolver.solve(res)
    
                # correct variables
                self.correct(q, dq, v, ddq, delta_q)
    
                # update system quantities
                Jac, res, f_ext = self.newton_raphson(q, dq, v, ddq, t, q_old, dq_old, v_old, ddq_old, t_old)
                res_abs = norm_of_vector(res)
                n_iter += 1

                if self.verbose:
                    if sp.sparse.issparse(Jac):
                        cond_nr = 0.0
                    else:
                        cond_nr = np.linalg.cond(Jac)
                    print('Iteration: {0:3d}, residual: {1:6.3E}, condition# of Jacobian: {2:6.3E}'.format(
                        n_iter, res_abs, cond_nr))

                if self.write_iter:
                    t_write = t + dt/1000000*n_iter
                    self.mechanical_system.write_timestep(t_write, q.copy())

                # catch failing convergence
                if n_iter > self.n_iter_max:
                    if self.conv_abort:
                        print(abort_statement)
                        self.iteration_info = np.array(self.iteration_info)
                        t_clock_end = time.time()
                        print('Time for time marching integration: {0:6.3f}s.'.format(t_clock_end - t_clock_start))
                        return

                    t = t_old
                    q = q_old.copy()
                    dq = dq_old.copy()
                    v = v_old.copy()
                    f_ext = f_ext_old.copy()
                    break

                # end of Newton-Raphson iteration loop

            print('Time: {0:3.6f}, #iterations: {1:3d}, residual: {2:6.3E}'.format(t, n_iter, res_abs))
            if self.track_niter:
                self.iteration_info.append((t, n_iter, res_abs))

            # end of time step loop

        self.linsolver.clear()

        # save iteration info
        self.iteration_info = np.array(self.iteration_info)

        # end time measurement
        t_clock_end = time.time()
        print('Time for time marching integration: {0:6.3f} seconds'.format(t_clock_end - t_clock_start))
        return


class LinearDynamicsSolver(Solver):
    '''
    General class for solving the linear dynamic problem of the mechanical system linearized around zero-displacement.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver.

    References
    ----------
       [1]  M. Géradin and D.J. Rixen (2015): Mechanical vibrations. Theory and
            application to structural dynamics. ISBN 978-1-118-90020-8.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, **options)

        # read options
        self.options = dict(**options)

        self.initial_conditions = self.set_initial_conditions(options['initial_conditions'])

        if 't0' in options:
            self.t0 = options['t0']
        else:
            print('Attention: No initial time was given for time-integration, setting t0 = 0.0.')
            self.t0 = 0.0

        if 't_end' in options:
            self.t_end = options['t_end']
        else:
            print('Attention: No end time was given for time-integration, setting t_end = 1.0.')
            self.t_end = 1.0

        if 'dt' in options:
            self.dt = options['dt']
        else:
            raise ValueError('Error: No time step size was given for the time integration.')

        if 'dt_output' in options:
            self.dt_output = options['dt_output']
        else:
            self.dt_output = self.dt

        if 'verbose' in options:
            self.verbose = options['verbose']
        else:
            self.verbose = False

        if 'use_v' in options:
            self.use_v = options['use_v']
        else:
            self.use_v = False
        return

    def set_initial_conditions(self, **options):
        if ('initial_conditions' in options) and ('q0' in options['initial_conditions']):
            q0 = options['initial_conditions']['q0']
            if len(q0) != self.mechanical_system.no_of_dofs:
                raise ValueError('Error: Dimension of q0 not valid for mechanical system.')
        else:
            print('Attention: No input for initial displacement is given, setting q0 = 0.')
            q0 = np.zeros(self.mechanical_system.no_of_dofs)

        if ('initial_conditions' in options) and ('dq0' in options['initial_conditions']):
            dq0 = options['initial_conditions']['dq0']
            if len(dq0) != self.mechanical_system.no_of_dofs:
                raise ValueError('Error: Dimension of dq0 is not valid for mechanical system.')
        else:
            print('Attention: No input for initial velocity is given, setting dq0 = 0.')
            dq0 = np.zeros(self.mechanical_system.no_of_dofs)
        return {'q0':q0, 'dq0':dq0}

    def effective_stiffness(self):
        pass

    def effective_force(self, q_old, dq_old, v_old, ddq_old, t, t_old):
        pass

    def update(self, q, q_old, dq_old, v_old, ddq_old):
        pass

    def solve(self):
        '''
        Solves the linear dynamic problem of the mechanical system linearized around zero-displacement.
    
        Parameters
        ----------

        '''

        # start time measurement
        t_clock_start = time.time()

        # initialize variables and set parameters
        self.mechanical_system.clear_timesteps()
        t = self.t0
        dt = self.dt
        time_range = np.arange(self.t0, self.t_end, self.dt_output)
        q = self.initial_conditions['q0'].copy()
        dq = self.initial_conditions['dq0'].copy()
        if self.use_v:
            v = self.initial_conditions['dq0'].copy()
        else:
            v = np.empty((0,0))
        ddq = np.zeros_like(dq)
        time_index = 0
        eps = 1E-13
        self.set_parameters(**self.options)

        # evaluate initial acceleration and LU-decompose effective stiffness
        K_eff = self.effective_stiffness()

        self.linsolver.set_A(self.mechanical_system.M_constr)
        ddq = self.linsolver.solve(self.mechanical_system.f_ext(q, dq, t)
                                   - self.mechanical_system.D_constr@dq \
                                   - self.mechanical_system.K_constr@q)

        self.linsolver.set_A(K_eff)
        if hasattr(self.linsolver, 'factorize'):
            self.linsolver.factorize()

        # time step loop
        while time_index < len(time_range):

            # write output
            if t + eps >= time_range[time_index]:
                self.mechanical_system.write_timestep(t, q.copy())
                time_index += 1
                if time_index == len(time_range):
                    break

            # save old variables
            q_old = q.copy()
            dq_old = dq.copy()
            v_old = v.copy()
            ddq_old = ddq.copy()
            t_old = t

            # solve system
            t += dt
            f_eff = self.effective_force(q_old, dq_old, v_old, ddq_old, t, t_old)

            q = self.linsolver.solve(f_eff)

            # update variables
            dq, v, ddq = self.update(q, q_old, dq_old, v_old, ddq_old)
            print('Time: {0:3.6f}'.format(t))

            # end of time step loop

        self.linsolver.clear()

        # end time measurement
        t_clock_end = time.time()
        print('Time for time marching integration: {0:6.3f} seconds'.format(t_clock_end - t_clock_start))
        return


# Special solvers derived from above
# ----------------------------------

class GeneralizedAlphaNonlinearDynamicsSolver(NonlinearDynamicsSolver):
    '''
    Class for solving the nonlinear dynamic problem of the mechanical system using the generalized-alpha time
    integration scheme.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver.

    References
    ----------
       [1]  J. Chung and G. Hulbert (1993): A time integration algorithm for structural 
            dynamics with improved numerical dissipation: the generalized-alpha method. 
            Journal of Applied Mechanics 60(2) 371--375.
       [2]  M. Géradin and D.J. Rixen (2015): Mechanical vibrations. Theory and 
            application to structural dynamics. ISBN 978-1-118-90020-8.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, **options)
        self.use_v = False
        if 'rho_inf' in options:
            self.rho_inf = options['rho_inf']
        else:
            self.rho_inf = 0.9
            print('Attention: No value for high frequency spectral radius was given, setting rho_inf = 0.9.')
        return

    def set_parameters(self, options):
        '''
        Set parameters for the nonlinear generalized-alpha time integration scheme.
        '''

        self.alpha_m = (2*self.rho_inf - 1)/(self.rho_inf + 1)
        self.alpha_f = self.rho_inf/(self.rho_inf + 1)
        self.beta = 0.25*(1 - self.alpha_m + self.alpha_f)**2
        self.gamma = 0.5 - self.alpha_m + self.alpha_f
        return

    def predict(self, q, dq, v, ddq):
        '''
        Predict variables for the nonlinear generalized-alpha time integration scheme.
        '''

        q += self.dt*dq + self.dt**2*(0.5 - self.beta)*ddq
        dq += self.dt*(1 - self.gamma)*ddq
        ddq *= 0
        return

    def newton_raphson(self, q, dq, v, ddq, t, q_old, dq_old, v_old, ddq_old, t_old):
        '''
        Return actual Jacobian and residuum for the nonlinear generalized-alpha time integration scheme.
        '''

        if self.mechanical_system.M_constr is None:
            self.mechanical_system.M()

        ddq_m = (1 - self.alpha_m)*ddq + self.alpha_m*ddq_old
        q_f = (1 - self.alpha_f)*q + self.alpha_f*q_old
        dq_f = (1 - self.alpha_f)*dq + self.alpha_f*dq_old
        t_f = (1 - self.alpha_f)*t + self.alpha_f*t_old

        K_f, f_f = self.mechanical_system.K_and_f(q_f, t_f)

        f_ext_f = self.mechanical_system.f_ext(q_f, dq_f, t_f)

        if self.mechanical_system.D_constr is None:
            Jac = -(1 - self.alpha_m)/(self.beta*self.dt**2) \
                    *self.mechanical_system.M_constr \
                  - (1 - self.alpha_f)*K_f
            res = f_ext_f - self.mechanical_system.M_constr@ddq_m - f_f
        else:
            Jac = -(1 - self.alpha_m)/(self.beta*self.dt**2) \
                    *self.mechanical_system.M_constr \
                  - (1 - self.alpha_f)*self.gamma/(self.beta*self.dt) \
                    *self.mechanical_system.D_constr \
                  - (1 - self.alpha_f)*K_f

            res = f_ext_f - self.mechanical_system.M_constr@ddq_m \
                  - self.mechanical_system.D_constr@dq_f - f_f
        return Jac, res, f_ext_f

    def correct(self, q, dq, v, ddq, delta_q):
        '''
        Correct variables for the nonlinear generalized-alpha time integration scheme.
        '''

        q += delta_q
        dq += self.gamma/(self.beta*self.dt)*delta_q
        ddq += 1/(self.beta*self.dt**2)*delta_q
        return


class JWHAlphaNonlinearDynamicsSolver(NonlinearDynamicsSolver):
    '''
    Class for solving the nonlinear dynamic problem of the mechanical system using the JWH-alpha time integration scheme.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver.

    References
    ----------
       [1]  K.E. Jansen, C.H. Whiting and G.M. Hulbert (2000): A generalized-alpha 
            method for integrating the filtered Navier-Stokes equations with a 
            stabilized finite element method. Computer Methods in Applied Mechanics and 
            Engineering 190(3) 305--319. DOI 10.1016/S0045-7825(00)00203-6.
       [2]  C. Kadapa, W.G. Dettmer and D. Perić (2017): On the advantages of using the 
            first-order generalised-alpha scheme for structural dynamic problems. 
            Computers and Structures 193 226--238. DOI 10.1016/j.compstruc.2017.08.013.
       [3]  M. Géradin and D.J. Rixen (2015): Mechanical vibrations. Theory and 
            application to structural dynamics. ISBN 978-1-118-90020-8.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, **options)
        self.use_v = True
        if 'rho_inf' in options:
            self.rho_inf = options['rho_inf']
        else:
            self.rho_inf = 0.9
            print('Attention: No value for high frequency spectral radius was given, setting rho_inf = 0.9.')
        return

    def set_parameters(self, options):
        '''
        Set parameters for the nonlinear JWH-alpha time integration scheme.
        '''

        self.alpha_m = (3 - self.rho_inf)/(2*(1 + self.rho_inf))
        self.alpha_f = 1/(1 + self.rho_inf)
        self.gamma = 0.5 + self.alpha_m - self.alpha_f
        return

    def predict(self, q, dq, v, ddq):
        '''
        Predict variables for the nonlinear JWH-alpha time integration scheme.
        '''

        q += self.dt*(self.alpha_m - self.gamma)/self.alpha_m*dq \
             + self.dt*self.gamma/self.alpha_m*v \
             + self.alpha_f*self.dt**2*self.gamma*(1 - self.gamma)/self.alpha_m*ddq
        dq += 1/self.alpha_m*(v - dq) \
              + self.alpha_f*self.dt*(1 - self.gamma)/self.alpha_m*ddq
        v += self.dt*(1 - self.gamma)*ddq
        ddq *= 0
        return

    def newton_raphson(self, q, dq, v, ddq, t, q_old, dq_old, v_old, ddq_old, t_old):
        '''
        Return actual Jacobian and residuum for the nonlinear JWH-alpha time integration scheme.
        '''

        if self.mechanical_system.M_constr is None:
            self.mechanical_system.M()

        ddq_m = self.alpha_m*ddq + (1 - self.alpha_m)*ddq_old
        q_f = self.alpha_f*q + (1 - self.alpha_f)*q_old
        v_f = self.alpha_f*v + (1 - self.alpha_f)*v_old
        t_f = self.alpha_f*t + (1 - self.alpha_f)*t_old

        K_f, f_f = self.mechanical_system.K_and_f(q_f, t_f)

        f_ext_f = self.mechanical_system.f_ext(q_f, v_f, t_f)

        if self.mechanical_system.D_constr is None:
            Jac = -self.alpha_m**2/(self.alpha_f*self.gamma**2*self.dt**2) \
                    *self.mechanical_system.M_constr \
                  - self.alpha_f*K_f
            res = f_ext_f - self.mechanical_system.M_constr@ddq_m - f_f
        else:
            Jac = -self.alpha_m**2/(self.alpha_f*self.gamma**2*self.dt**2) \
                    *self.mechanical_system.M_constr \
                  - self.alpha_m/(self.gamma*self.dt)*self.mechanical_system.D_constr \
                  - self.alpha_f*K_f
            res = f_ext_f - self.mechanical_system.M_constr@ddq_m \
                  - self.mechanical_system.D_constr@v_f - f_f
        return Jac, res, f_ext_f

    def correct(self, q, dq, v, ddq, delta_q):
        '''
        Correct variables for the nonlinear JWH-alpha time integration scheme.
        '''

        q += delta_q
        dq += 1/(self.gamma*self.dt)*delta_q
        v += self.alpha_m/(self.alpha_f*self.gamma*self.dt)*delta_q
        ddq += self.alpha_m/(self.alpha_f*self.gamma**2*self.dt**2)*delta_q
        return


class GeneralizedAlphaLinearDynamicsSolver(LinearDynamicsSolver):
    '''
    Class for solving the linear dynamic problem of the mechanical system linearized around zero-displacement using the
    generalized-alpha time integration scheme.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver.

    References
    ----------
       [1]  J. Chung and G. Hulbert (1993): A time integration algorithm for structural 
            dynamics with improved numerical dissipation: the generalized-alpha method. 
            Journal of Applied Mechanics 60(2) 371--375.
       [2]  M. Géradin and D.J. Rixen (2015): Mechanical vibrations. Theory and 
            application to structural dynamics. ISBN 978-1-118-90020-8.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, **options)
        self.use_v = False
        if 'rho_inf' in options:
            self.rho_inf = options['rho_inf']
        else:
            self.rho_inf = 0.9
            print('Attention: No value for high frequency spectral radius was given, setting rho_inf = 0.9.')
        return

    def set_parameters(self, dt, options):
        '''
        Set parameters for the linear generalized-alpha time integration scheme.
        '''

        self.alpha_m = (2*self.rho_inf - 1)/(self.rho_inf + 1)
        self.alpha_f = self.rho_inf/(self.rho_inf + 1)
        self.beta = 0.25*(1 - self.alpha_m + self.alpha_f)**2
        self.gamma = 0.5 - self.alpha_m + self.alpha_f
        return

    def effective_stiffness(self):
        '''
        Return effective stiffness matrix for linear generalized-alpha time integration 
        scheme.
        '''

        self.mechanical_system.M()
        self.mechanical_system.D_constr = self.mechanical_system.D()
        self.mechanical_system.K_constr = self.mechanical_system.K()

        K_eff = (1 - self.alpha_m)/(self.beta*self.dt**2)*self.mechanical_system.M_constr \
                + (1 - self.alpha_f)*self.gamma/(self.beta*self.dt)*self.mechanical_system.D_constr \
                + (1 - self.alpha_f)*self.mechanical_system.K_constr
        return K_eff

    def effective_force(self, q_old, dq_old, v_old, ddq_old, t, t_old):
        '''
        Return actual effective force for linear generalized-alpha time integration scheme.
        '''

        t_f = (1 - self.alpha_f)*t + self.alpha_f*t_old

        f_ext_f = self.f_ext(None, None, t_f)

        F_eff = ((1 - self.alpha_m)/(self.beta*self.dt**2)*self.mechanical_system.M_constr \
                + (1 - self.alpha_f)*self.gamma/(self.beta*self.dt)*self.mechanical_system.D_constr \
                - self.alpha_f*self.mechanical_system.K_constr)@q_old \
                + ((1 - self.alpha_m)/(self.beta*self.dt)*self.mechanical_system.M_constr \
                - (self.gamma*(self.alpha_f - 1) + self.beta)/self.beta*self.mechanical_system.D_constr)@dq_old \
                + (-(0.5*(self.alpha_m - 1) + self.beta)/self.beta*self.mechanical_system.M_constr \
                - (1 - self.alpha_f)*(self.beta - 0.5*self.gamma)*self.dt/self.beta*self.mechanical_system.D_constr)@ddq_old \
                + f_ext_f
        return F_eff

    def update(self, q, q_old, dq_old, v_old, ddq_old):
        '''
        Return actual velocity and acceleration for linear generalized-alpha time integration scheme.
        '''

        ddq = 1/(self.beta*self.dt**2)*(q - q_old) - 1/(self.beta*self.dt)*dq_old - (0.5 - self.beta)/self.beta*ddq_old
        v = np.empty((0,0))
        dq = dq_old + self.dt*((1 - self.gamma)*ddq_old + self.gamma*ddq)
        return dq, v, ddq


class JWHAlphaLinearDynamicsSolver(LinearDynamicsSolver):
    '''
    Class for solving the linear dynamic problem of the mechanical system linearized 
    around zero-displacement using the JWH-alpha time integration scheme.

    Parameters
    ----------
    mechanical_system : Instance of MechanicalSystem
        Mechanical system to be solved.
    options : Dictionary
        Options for solver.

    References
    ----------
       [1]  K.E. Jansen, C.H. Whiting and G.M. Hulbert (2000): A generalized-alpha 
            method for integrating the filtered Navier-Stokes equations with a 
            stabilized finite element method. Computer Methods in Applied Mechanics and 
            Engineering 190(3) 305--319. DOI 10.1016/S0045-7825(00)00203-6.
       [2]  C. Kadapa, W.G. Dettmer and D. Perić (2017): On the advantages of using the 
            first-order generalised-alpha scheme for structural dynamic problems. 
            Computers and Structures 193 226--238. DOI 10.1016/j.compstruc.2017.08.013.
       [3]  M. Géradin and D.J. Rixen (2015): Mechanical vibrations. Theory and 
            application to structural dynamics. ISBN 978-1-118-90020-8.
    '''

    def __init__(self, mechanical_system, **options):
        super().__init__(mechanical_system, **options)
        self.use_v = True
        if 'rho_inf' in options:
            self.rho_inf = options['rho_inf']
        else:
            self.rho_inf = 0.9
            print('Attention: No value for high frequency spectral radius was given, setting rho_inf = 0.9.')
        return

    def set_parameters(self, dt, options):
        '''
        Set parameters for the nonlinear JWH-alpha time integration scheme.
        '''

        self.alpha_m = (3 - self.rho_inf)/(2*(1 + self.rho_inf))
        self.alpha_f = 1/(1 + self.rho_inf)
        self.gamma = 0.5 + self.alpha_m - self.alpha_f
        return

    def effective_stiffness(self):
        '''
        Return effective stiffness matrix for linear JWH-alpha time integration scheme.
        '''

        self.mechanical_system.M()
        self.mechanical_system.D_constr = self.mechanical_system.D()
        self.mechanical_system.K_constr = self.mechanical_system.K()

        K_eff = self.alpha_m**2/(self.alpha_f*self.gamma**2*self.dt**2)*self.mechanical_system.M_constr \
                + self.alpha_m/(self.gamma*self.dt)*self.mechanical_system.D_constr \
                + self.alpha_f*self.mechanical_system.K_constr
        return K_eff

    def effective_force(self, q_old, dq_old, v_old, ddq_old, t, t_old):
        '''
        Return actual effective force for linear JWH-alpha time integration scheme.
        '''

        t_f = self.alpha_f*t + (1 - self.alpha_f)*t_old

        f_ext_f = self.mechanical_system.f_ext(None, None, t_f)

        F_eff = (-(1 - self.alpha_f)*self.mechanical_system.K_constr \
                + self.alpha_m/(self.gamma*self.dt)*self.mechanical_system.D_constr \
                + self.alpha_m**2/(self.alpha_f*self.gamma**2*self.dt**2)*self.mechanical_system.M_constr)@q_old \
                + (-(self.gamma - self.alpha_m)/self.gamma*self.mechanical_system.D_constr \
                - self.alpha_m*(self.gamma - self.alpha_m)/(self.alpha_f*self.gamma**2*self.dt)*self.mechanical_system.M_constr)@dq_old \
                + (self.alpha_m/(self.alpha_f*self.gamma*self.dt)*self.mechanical_system.M_constr)@v_old \
                + (-(self.gamma - self.alpha_m)/self.gamma*self.mechanical_system.M_constr)@ddq_old \
                + f_ext_f
        return F_eff

    def update(self, q, q_old, dq_old, v_old, ddq_old):
        '''
        Return actual velocity and acceleration for linear JWH-alpha time integration scheme.
        '''

        dq = 1/(self.gamma*self.dt)*(q - q_old) + (self.gamma - 1)/self.gamma*dq_old
        v = self.alpha_m/self.alpha_f*dq + (1 - self.alpha_m)/self.alpha_f*dq_old \
            + (self.alpha_f - 1)/self.alpha_f*v_old
        ddq = 1/(self.gamma*self.dt)*(v - v_old) + (self.gamma - 1)/self.gamma*ddq_old
        return dq, v, ddq


class ConstraintSystemSolver(NonlinearDynamicsSolver):
    # TBD
    pass


# This could be a dictionary for a convenient mapping of scheme names (strings) to their solver classes
solvers_available = {'NonlinearStatics' : NonlinearStaticsSolver,
                     'LinearStatics' : LinearStaticsSolver,
                     'NonlinearGeneralizedAlpha' : GeneralizedAlphaNonlinearDynamicsSolver,
                     'NonlinearJWHAlpha' : JWHAlphaNonlinearDynamicsSolver,
                     'LinearGeneralizedAlpha' : GeneralizedAlphaLinearDynamicsSolver,
                     'LinearJWHAlpha' : JWHAlphaLinearDynamicsSolver}


def choose_solver(mechanical_system, **options):
    if type(mechanical_system) == MechanicalSystem:
        solvertype = options['solvertype']

    solver = solvers_available[solvertype](**options)
    return solver


def norm_of_vector(array):
    '''
    Compute the 2-norm of a vector.

    Parameters
    ----------
    array : ndarray
        one dimensional array

    Returns
    -------
    abs : float
        2-norm of the given array.

    '''
    return np.sqrt(array.T.dot(array))

