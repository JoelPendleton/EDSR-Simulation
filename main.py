import kwant.continuum
import numpy as np
import matplotlib.pyplot as plt
import kwant
from numpy import vectorize
from matplotlib import animation

class System:
    def __init__(self, hamiltonian, lattices):
        # constants in SI
        self.hbar_SI = 1.054571817e-34
        self.e_SI = 1.602176634e-19
        self.a_0_SI = 5.2917721090380e-11
        self.total_length_m = 7820e-9
        self.B_0_SI = 100e-3
        self.b_sl_SI = 250e-3
        self.time = 0
        # Constants in a.u.
        self.hbar = 1
        self.g = 2
        self.m = 1
        self.e = 1
        self.total_length_au = self.total_length_m / self.a_0_SI # Total distance of nanotube in terms of au
        self.lattices = lattices
        self.lattice_size = self.total_length_au / self.lattices # The distance in atomic units spanned by a lattice point
        self.mu_B = self.e * self.hbar / (2 * self.m)
        self.a_0 = 1
        self.pulse_frequency = 240 # in Hz
        self.pulse_velocity = self.pulse_frequency * self.total_length_au # in au/s
        self.hamiltonian = hamiltonian
        self.template = kwant.continuum.discretize(hamiltonian)
        self.gaussian_mu = 0
        self.a = 1

    def tesla_SI_to_au(self, tesla):
        """
        Function to convert the magnetic flux density from SI units to AU units
        :param tesla: the magnetic flux density in teslas.
        :return: the magnetic flux density in AU.
        """
        return tesla / (self.hbar_SI/(self.e_SI * (self.a_0_SI ** 2)))

    def hartreeToeV(self,hartree):
        return hartree * 27.2114

    def auTonm(self, au):
        return 0.0529177249 * au

    def make_system(self):
        """
        Function to create the system
        :param length: the length of the nanotube
        :return: the system object
        """

        # We need to have 1d since the hamiltonian is 1d otherwise it can't be applied
        def shape(site):
            """
            function to define the shape of the scattering region.
            :param site: the current site.
            :return: the a boolean saying whether the scattering site should be drawn
            """
            (x, ) = site.pos
            return (0 <= x < self.lattices)

        self.syst = kwant.Builder()

        #Add the nanotube to the system
        self.syst.fill(self.template, shape, (0, ));

        kwant.plot(self.syst, file='./figures/shape.png');
        self.syst = self.syst.finalized()
        return self.syst



    def gaussian(self, x, sig):
        """
        Function to compute a gaussian pulse.
        :param x: the coordinate value
        :param mu: the centre of the gaussian
        :param sig: the standard deviation
        :return: the gaussian function values.
        """

        return np.exp(-np.power(x - self.gaussian_mu - self.pulse_velocity * self.time , 2.) / (2 * np.power(sig, 2.)))

    def potential(self, x):  # Infinite square well
        """
        Function to define the potential of the lead.
        :param x: the position in the system.
        :return: the potential energy.
        """
        if 0 <= x <= self.total_length_au:
            return 0.002 * self.gaussian(x, self.total_length_au / 14)
        else:
            return 999999999

    def kwantPotential(self, x):
        """
        Potential that kwant uses. It inputs lattice points coord. so we need to convert to au to use our
        other functions
        :param x:
        :return: potential after conversion to au
        """
        return self.potential(x * self.lattice_size) # Kwant uses lattice points so need scaling

    def eigenstates(self):
        """
        Function to compute the eigenstates of the system.
        :param syst: the system object.
        :return: the sorted eigenvalues and eigenvectors.
        """
        B_0_au = self.tesla_SI_to_au(self.B_0_SI)
        b_sl_au = self.tesla_SI_to_au(self.b_sl_SI)  # in hbar/(e*(a_0)**2)
        self.A_constant =  -self.g * self.mu_B * B_0_au * self.hbar / 2
        self.B_constant = -self.g * self.mu_B * b_sl_au * self.hbar / 2
        self.C_constant = self.hbar ** 2 / (2 * self.m)
        params = dict(A=self.A_constant, B=self.B_constant, C=self.C_constant, V=self.kwantPotential)
        # Calculate the wave functions in the system.
        h = self.syst.hamiltonian_submatrix(params=params)

        eigenValues, eigenVectors = np.linalg.eig(h)

        idx = eigenValues.argsort()
        eigenValues = np.real(eigenValues[idx])
        eigenVectors = eigenVectors[:, idx]

        # For each eigenvalue for each spin we get two eigenvectors and for each position there are two possible spins
        # so we have four eigenvectors for each position along the nanotube.


        return eigenValues, eigenVectors

    def showEnergies(self):
        """
        Procedure to display the potential and energy levels of the system
        :param syst: the system object.
        :return:
        """
        self.gaussian_mu = self.total_length_au /4
        eigenValues, eigenVectors = self.eigenstates()
        x_coordinates = np.linspace(0, self.total_length_au , self.lattices)
        vpotential = vectorize(self.potential)

        y_coordinates = vpotential(x_coordinates)
        plt.figure()
        plt.plot(x_coordinates, y_coordinates, label="$V(x)$")
        E_1 = eigenValues[0]
        E_2 = eigenValues[1]
        E_3 = eigenValues[2]

        # print("The energies of the ground and excited states are {0} and {1}, respectively.".format(E_1, E_2))
        plt.plot([0, np.max(x_coordinates)], [E_1, E_1], label="$E_1$")
        plt.plot([0, np.max(x_coordinates)], [E_2, E_2], label="$E_2$")
        plt.plot([0, np.max(x_coordinates)], [E_3, E_3], label="$E_3$", linestyle='dashed')
        plt.xlabel("$x (au$)")
        plt.ylabel("$E (H)$")
        plt.legend(loc="upper right")
        plt.savefig("./figures/Energies/energies-{}.svg".format(self.time))  # With A = 0 we expect straight forward zeeman splitting
        plt.close()
        print("Plot of energies saved.")

    def showWavefunction(self, animate=False):

        """
        Procedure to show the probability density function.
        :param syst: the system object.
        :return:
        """

        eigenValues, eigenVectors = self.eigenstates()


        x_coords = np.linspace(0, self.total_length_au, self.lattices)

        psi1 = np.abs(eigenVectors[0::2,0])**2 + np.abs(eigenVectors[1::2,0])**2 +\
                   np.abs(eigenVectors[0::2,1])**2+ np.abs(eigenVectors[1::2, 1])**2

        psi2 = np.abs(eigenVectors[0::2, 2]) ** 2 + np.abs(eigenVectors[1::2, 2]) ** 2 + \
               np.abs(eigenVectors[0::2, 3]) ** 2 + np.abs(eigenVectors[1::2, 3]) ** 2

        if animate:
            return x_coords,psi1, psi2

        else:
            plt.figure()
            plt.plot(x_coords, psi1, label="n=1")
            plt.plot(x_coords, psi2, label="n=2")


            plt.xlabel("x (au)")
            plt.ylabel("$|\psi(x)|^2$")
            plt.legend(loc="upper right")
            plt.savefig("./figures/PDFs/pdf-{}.svg".format(self.time))  # With A = 0 we expect straight forward zeeman splitting
            plt.close()
            print("Plot of wave functions saved!")
            return True



    def animateWavefunction(self):
        self.gaussian_mu = 0 # self.total_length_au / 4
        # create a figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1)
        x, y1,y2 = self.showWavefunction(animate=True)
        vpotential = vectorize(self.potential)
        y3 = vpotential(x)

        # intialize two line objects (one in each axes)
        line1, = ax1.plot([], [], lw=2, label='$n=1$')
        line2, = ax1.plot([], [], lw=2,label='$n=2$')
        line3, = ax2.plot([], [], lw=2, color='r', label='$V(x)$')
        line = [line1, line2, line3]
        xmax = self.auTonm(np.max(x))
        ax1.set_xlim(0, xmax)
        ax1.set_ylim(0, np.max(y1) * 1.2)
        ax2.set_xlim(0, xmax)
        ax2.set_ylim(0, self.hartreeToeV(np.max(y3) * 1.5))

        plt.xlabel("x (nm)")
        ax1.set_ylabel("$|\psi(x)|^2$")
        ax2.set_ylabel("$E$ (eV)")
        fig.suptitle("Wave Functions Inside a Time-varying Position at $t=0s$")
        number_of_frames = 200  # Takes [number_of_frames] time steps at frequency provided for pulse to travel along the
                               # the nanotube.

        # initialization function: plot the background of each frame
        def init():
            line[0].set_data([], [])
            line[1].set_data([], [])
            line[2].set_data([], [])

            return line

        def animate(i):
            self.time =  (i / (self.pulse_frequency)) / number_of_frames
            fig.suptitle("Wave Functions Inside a Time-varying Position at $t={}s$".format('{:g}'.format(float('{:.{p}g}'.format(self.time, p=2)))))



            x, y1,y2 = self.showWavefunction(animate=True)

            vpotential = vectorize(self.potential)
            y3 = vpotential(x)
            x = self.auTonm(x)
            line[0].set_data(x, y1)
            line[1].set_data(x, y2)
            line[2].set_data(x, self.hartreeToeV(y3))
            ax1.legend(loc="upper right")
            ax2.legend(loc="upper right")

            return line

        # call the animator.  blit=True means only re-draw the parts that have changed.
        anim = animation.FuncAnimation(fig, animate,init_func=init,
                                       frames=number_of_frames, interval=30, blit=True)

        # save the animation as an mp4.  This requires ffmpeg or mencoder to be
        # installed.  The extra_args ensure that the x264 codec is used, so that
        # the video can be embedded in html5.  You may need to adjust this for
        # your system: for more information, see
        # http://matplotlib.sourceforge.net/api/animation_api.html
        anim.save('wavefunction-animation.mp4', writer='ffmpeg')
        plt.close()
        print("Animation of wave function saved!")

def main():
    lattices = 100

    system1 = System("(C * k_x**2 + V(x)) * identity(2) + A * sigma_x + B * x * sigma_y", lattices)
    system1.make_system()
    system1.animateWavefunction()
    system1.time = 0
    system1.gaussian_mu = system1.lattices * system1.lattice_size / 4
    system1.showEnergies()
    system1.showWavefunction()


if __name__ == '__main__':
    main()

# Output magnetic field profiles along the wire (mT) from mumax simulation

# Add pulse gaussian along the wire depending on time
# Compute the probability of occupation of state 2 as time varies
# Display energy levels, display potential energy
# Make code OOP


# Fix scaling to give it in-terms of eV -> give in terms of a.u.
