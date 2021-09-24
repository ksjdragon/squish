from __future__ import annotations
from typing import List, Union, Optional, Iterator
import pickle, numpy as np
from pathlib import Path
from _squish import AreaEnergy, RadialALEnergy, RadialTEnergy

OUTPUT_DIR = Path("squish_output")
OUTPUT_DIR.mkdir(exist_ok=True)

STR_TO_ENERGY = {
	"area": AreaEnergy,
	"radial-al": RadialALEnergy,
	"radial-t" : RadialTEnergy
}


def generate_filepath(sim: SimulationMode, fol: Union[str, Path]) -> Path:
	energy = sim.energy.title_str
	width, height = round(sim.domain.w, 2), round(sim.domain.h, 2)

	base_path = f"{fol}/{energy}{sim.title_str} - N{sim.domain.n} - {width:.2f}x{height:.2f}"

	i = 1
	real_path = Path(base_path)
	while real_path.is_dir():
		real_path = Path(f"{base_path}({i})")
		i += 1

	return real_path


def torus_sites(n: int, w: float, h: float, L: Tuple[int, int]) -> numpy.ndarray:
	dim = np.array([[w, h]])
	L = np.array(L)
	return (np.array([1,1])/2 + np.concatenate([(i*dim*L/n) for i in range(n)])) % dim


class DomainParams:
	"""Container for basic domain parameters

	Attributes:
		n (int): Number of sites in simulation.
		w (float): width of the bounding domain.
		h (float): height of the bounding domain.
		r (float): natural radius of the objects.
		dim (np.ndarray): dimensions, w x h.

	"""

	__slots__ = ['n', 'w', 'h', 'r', 'dim']


	def __init__(self, n: int, w: float, h: float, r: float) -> None:
		if n < 2:
			raise ValueError("Number of objects should be larger than 2!")

		if w <= 0:
			raise ValueError("Width needs to be nonzero and positive!")

		if h <= 0:
			raise ValueError("Height needs to be nonzero and positive!")

		self.n, self.w, self.h, self.r = int(n), float(w), float(h), float(r)
		self.dim = np.array([self.w, self.h])


	def __iter__(self) -> Iterator:
		return iter((self.n, self.w, self.h, self.r))

	def __str__(self) -> str:
		return f"N = {self.n}, R = {self.r}, {self.w} X {self.h}"


class Energy:
	"""Generic container for energies.

	Attributes:
		mode (VoronoiContainer): VoronoiContainer for the chosen energy.

	"""

	__slots__ = ['mode']


	def __init__(self, mode: Union[str, VoronoiContainer]) -> None:
		if isinstance(mode, str):
			try:
				self.mode = STR_TO_ENERGY[mode.lower()]
			except KeyError:
				raise ValueError(f"\'{mode}\' is not a valid energy!")
		else:
			if mode is not VoronoiContainer and issubclaass(mode, VoronoiContainer):
				raise ValueError("Provided class is not a valid energy!")
			self.mode = mode


	@property
	def attr_str(self) -> str:
		return self.mode.attr_str


	@property
	def title_str(self) -> str:
		return self.mode.title_str


class Simulation:
	"""Generic container for simulations.

	Attributes:
		domain (DomainParams): Domain Parameters for this simulation.
		energy (Energy): energy being used for caluclations.
		path (Path): Path to location of where to store simulation files.
		frames (List[VoronoiContainer]): Stores frames of the simulation.

	"""

	__slots__ = ['domain', 'energy', 'path', 'frames']

	def __init__(self, domain: DomainParams, energy: Energy, name: Optional[str] = None) -> None:
		self.domain, self.energy = domain, energy
		self.frames = []

		if name is None:
			self.path = generate_filepath(self, OUTPUT_DIR)
		else:
			self.path = OUTPUT_DIR / name

		self.path.mkdir()


	def __iter__(self) -> Iterator:
		return iter(self.frames)

	def __getitem__(self, key: int) -> Energy:
		return self.frames[key]


	def __len__(self) -> int:
		return len(self.frames)


	def add_frame(self, points: Optional[numpy.ndarray]) -> None:
		if points is None:
			points = np.random.random_sample((self.domain.n, 2)) * self.domain.dim
		else:
			if points.shape[1] != 2 or len(points.shape) > 2:
				raise ValueError("Sites should be 2 dimensional!")

			if points.shape[0] != self.domain.n:
				raise ValueError("Number of sites provided do not match the array!")

		self.frames.append(self.energy.mode(*self.domain, points % self.domain.dim))


	def get_distinct(self) -> List[int]:
		"""Gets the distinct configurations based on the average radii of the sites.
		and returns the number of configurations for each distinct configuration.
		"""

		distinct_avg_radii, distinct_count, new_frames = [], [], []

		for frame in self.frames:
			avg_radii = np.sort(frame.stats["avg_radius"])
			is_in = False
			for i, dist_radii in enumerate(distinct_avg_radii):
				if np.allclose(avg_radii, dist_radii, atol=1e-5):
					is_in = True
					distinct_count[i] += 1
					break

			if not is_in:
				distinct_avg_radii.append(avg_radii)
				new_frames.append(frame)

		self.frames = new_frames
		return distinct_count


	def save(self, info: Dict) -> None:
		path = self.path / 'data.squish'

		with open(path, 'wb') as out:
			pickle.dump(info, out, pickle.HIGHEST_PROTOCOL)


	def frame_data(self, index: int) -> None:
		f = self[index]
		info = {
			"arr": f.site_arr,
			"domain": (f.n, f.h, f.w, f.r),
			"energy": f.attr_str,
			"stats": f.stats
		}
		return info

		# all_info = []
		# for frame in self.frames:
		# 	frame_info = dict()
		# 	frame_info["arr"] = frame.site_arr
		# 	frame_info["energy"] = {AreaEnergy: "area", RadialALEnergy: "radial-al",
		# 							RadialTEnergy: "radial-t"}[self.energy]
		# 	frame_info["params"] = (frame.n, frame.w, frame.h, frame.r)
		# 	all_info.append(frame_info)

		# class_name = {Flow: "flow", Search: "search", Shrink: "shrink"}[self.__class__]

		# with open(path, 'wb') as output:
		# 	pickle.dump((all_info, class_name), output, pickle.HIGHEST_PROTOCOL)
		# print("Wrote to " + path, flush=True)


	@staticmethod
	def load(path: str) -> Simulation:
		with open(path, 'rb') as infile:
			while True:
				try:
					yield pickle.load(infile)
				except EOFError:
					break


	@staticmethod
	def load_old(filename: str) -> Simulation:
		"""
		Loads the points at every point into a file.
		:param filename: [str] name of the file
		"""
		frames = []
		with open(filename, 'rb') as data:
			all_info, sim_class = pickle.load(data)
			if type(sim_class) == str:
				sim_class = {"flow": Flow, "search": Search, "shrink": Shrink}[sim_class]


			sim = sim_class(*all_info[0]["params"], "radial-t", 0,0)
			for frame_info in all_info:
				frames.append(sim.energy(*frame_info["params"], frame_info["arr"]))
				#frames[-1].stats = frame_info["stats"]

			sim.frames = frames
		return sim
