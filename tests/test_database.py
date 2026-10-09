import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base
from src.database.repository import TransitRepository


class TestDatabaseRepository(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionFactory = sessionmaker(bind=self.engine)
        self.session = SessionFactory()
        self.repo = TransitRepository(self.session)

    def tearDown(self):
        self.session.close()

    def test_save_and_retrieve_vehicle_positions(self):
        records = [
            {
                "timestamp": 1720000100,
                "vehicle_id": "BUS_01",
                "trip_id": "T1",
                "route_id": "534",
                "latitude": 28.525,
                "longitude": 77.210,
                "current_stop_sequence": 2,
            },
            {
                "timestamp": 1720000100,
                "vehicle_id": "BUS_02",
                "trip_id": "T2",
                "route_id": "534",
                "latitude": 28.530,
                "longitude": 77.215,
                "current_stop_sequence": 4,
            },
        ]

        count = self.repo.save_vehicle_positions(records)
        self.assertEqual(count, 2)

        positions = self.repo.get_latest_positions()
        self.assertEqual(len(positions), 2)

        route_positions = self.repo.get_route_latest_positions("534")
        self.assertEqual(len(route_positions), 2)

        history = self.repo.get_vehicle_history("BUS_01")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].vehicle_id, "BUS_01")


if __name__ == "__main__":
    unittest.main()
