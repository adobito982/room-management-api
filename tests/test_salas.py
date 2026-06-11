"""Test cases for sala endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.schemas import SalaCreate

# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_test.db"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override get_db dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup and teardown test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check(self):
        """Test health check returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self):
        """Test root endpoint returns information."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "Room Management API"


class TestCreateSala:
    """Test sala creation."""

    def test_create_sala_success(self):
        """Test successful sala creation."""
        sala_data = {
            "nombre": "Sala de Conferencias A",
            "ubicacion": "Piso 2",
            "capacidad": 20,
            "equipamiento": ["Proyector", "Whiteboard"],
        }
        response = client.post("/salas", json=sala_data)
        assert response.status_code == 201
        data = response.json()
        assert data["nombre"] == sala_data["nombre"]
        assert data["ubicacion"] == sala_data["ubicacion"]
        assert data["capacidad"] == sala_data["capacidad"]
        assert data["equipamiento"] == sala_data["equipamiento"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_sala_minimal(self):
        """Test sala creation with minimal fields."""
        sala_data = {
            "nombre": "Sala Simple",
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        response = client.post("/salas", json=sala_data)
        assert response.status_code == 201
        data = response.json()
        assert data["equipamiento"] == []

    def test_create_sala_invalid_capacity(self):
        """Test sala creation with invalid capacity."""
        sala_data = {
            "nombre": "Sala Invalid",
            "ubicacion": "Piso 1",
            "capacidad": 0,
        }
        response = client.post("/salas", json=sala_data)
        assert response.status_code == 422

    def test_create_sala_capacity_too_high(self):
        """Test sala creation with capacity exceeding limit."""
        sala_data = {
            "nombre": "Sala Invalid",
            "ubicacion": "Piso 1",
            "capacidad": 1001,
        }
        response = client.post("/salas", json=sala_data)
        assert response.status_code == 422

    def test_create_sala_duplicate_name(self):
        """Test sala creation with duplicate name."""
        sala_data = {
            "nombre": "Sala Unica",
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        response1 = client.post("/salas", json=sala_data)
        assert response1.status_code == 201

        response2 = client.post("/salas", json=sala_data)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    def test_create_sala_missing_required_field(self):
        """Test sala creation with missing required field."""
        sala_data = {
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        response = client.post("/salas", json=sala_data)
        assert response.status_code == 422

    def test_create_sala_empty_name(self):
        """Test sala creation with empty name."""
        sala_data = {
            "nombre": "",
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        response = client.post("/salas", json=sala_data)
        assert response.status_code == 422


class TestGetSala:
    """Test getting a specific sala."""

    def test_get_sala_success(self):
        """Test getting an existing sala."""
        # Create a sala first
        sala_data = {
            "nombre": "Sala Test",
            "ubicacion": "Piso 1",
            "capacidad": 15,
        }
        create_response = client.post("/salas", json=sala_data)
        sala_id = create_response.json()["id"]

        # Get the sala
        response = client.get(f"/salas/{sala_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sala_id
        assert data["nombre"] == sala_data["nombre"]

    def test_get_sala_not_found(self):
        """Test getting a non-existent sala."""
        response = client.get("/salas/9999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestGetAllSalas:
    """Test getting all salas with pagination."""

    def test_get_salas_empty(self):
        """Test getting salas when database is empty."""
        response = client.get("/salas")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["skip"] == 0
        assert data["limit"] == 10

    def test_get_salas_with_items(self):
        """Test getting salas with items."""
        # Create multiple salas
        for i in range(3):
            sala_data = {
                "nombre": f"Sala {i}",
                "ubicacion": f"Piso {i}",
                "capacidad": 10 + i,
            }
            client.post("/salas", json=sala_data)

        response = client.get("/salas")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_get_salas_pagination_skip(self):
        """Test getting salas with skip parameter."""
        # Create multiple salas
        for i in range(5):
            sala_data = {
                "nombre": f"Sala {i}",
                "ubicacion": f"Piso {i}",
                "capacidad": 10 + i,
            }
            client.post("/salas", json=sala_data)

        response = client.get("/salas?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["skip"] == 2
        assert data["limit"] == 2
        assert data["total"] == 5

    def test_get_salas_pagination_limit_exceeded(self):
        """Test limit parameter validation."""
        response = client.get("/salas?limit=101")
        assert response.status_code == 400

    def test_get_salas_pagination_negative_skip(self):
        """Test skip parameter validation."""
        response = client.get("/salas?skip=-1")
        assert response.status_code == 400

    def test_get_salas_default_limit(self):
        """Test default limit value."""
        # Create 15 salas
        for i in range(15):
            sala_data = {
                "nombre": f"Sala {i}",
                "ubicacion": f"Piso {i}",
                "capacidad": 10,
            }
            client.post("/salas", json=sala_data)

        response = client.get("/salas")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["limit"] == 10


class TestUpdateSala:
    """Test updating salas."""

    def test_update_sala_success(self):
        """Test successful sala update."""
        # Create a sala
        sala_data = {
            "nombre": "Sala Original",
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        create_response = client.post("/salas", json=sala_data)
        sala_id = create_response.json()["id"]

        # Update the sala
        update_data = {
            "nombre": "Sala Actualizada",
            "capacidad": 20,
        }
        response = client.put(f"/salas/{sala_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Sala Actualizada"
        assert data["capacidad"] == 20
        assert data["ubicacion"] == "Piso 1"  # Unchanged field

    def test_update_sala_partial(self):
        """Test partial sala update."""
        # Create a sala
        sala_data = {
            "nombre": "Sala Original",
            "ubicacion": "Piso 1",
            "capacidad": 10,
            "equipamiento": ["Proyector"],
        }
        create_response = client.post("/salas", json=sala_data)
        sala_id = create_response.json()["id"]

        # Update only name
        update_data = {"nombre": "Sala Renombrada"}
        response = client.put(f"/salas/{sala_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Sala Renombrada"
        assert data["capacidad"] == 10
        assert data["equipamiento"] == ["Proyector"]

    def test_update_sala_not_found(self):
        """Test updating a non-existent sala."""
        update_data = {"nombre": "Sala Nueva"}
        response = client.put("/salas/9999", json=update_data)
        assert response.status_code == 404

    def test_update_sala_empty_object(self):
        """Test update with empty object."""
        # Create a sala
        sala_data = {
            "nombre": "Sala Test",
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        create_response = client.post("/salas", json=sala_data)
        sala_id = create_response.json()["id"]

        # Update with empty object
        response = client.put(f"/salas/{sala_id}", json={})
        assert response.status_code == 200

    def test_update_sala_invalid_capacity(self):
        """Test update with invalid capacity."""
        # Create a sala
        sala_data = {
            "nombre": "Sala Test",
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        create_response = client.post("/salas", json=sala_data)
        sala_id = create_response.json()["id"]

        # Update with invalid capacity
        update_data = {"capacidad": 0}
        response = client.put(f"/salas/{sala_id}", json=update_data)
        assert response.status_code == 422


class TestDeleteSala:
    """Test deleting salas."""

    def test_delete_sala_success(self):
        """Test successful sala deletion."""
        # Create a sala
        sala_data = {
            "nombre": "Sala Eliminar",
            "ubicacion": "Piso 1",
            "capacidad": 10,
        }
        create_response = client.post("/salas", json=sala_data)
        sala_id = create_response.json()["id"]

        # Delete the sala
        response = client.delete(f"/salas/{sala_id}")
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify it's deleted
        get_response = client.get(f"/salas/{sala_id}")
        assert get_response.status_code == 404

    def test_delete_sala_not_found(self):
        """Test deleting a non-existent sala."""
        response = client.delete("/salas/9999")
        assert response.status_code == 404


class TestSearchByNombre:
    """Test searching salas by name."""

    def test_search_by_nombre_found(self):
        """Test successful search by name."""
        # Create salas
        sala_data1 = {
            "nombre": "Sala de Conferencias",
            "ubicacion": "Piso 1",
            "capacidad": 20,
        }
        sala_data2 = {
            "nombre": "Sala de Reuniones",
            "ubicacion": "Piso 2",
            "capacidad": 10,
        }
        client.post("/salas", json=sala_data1)
        client.post("/salas", json=sala_data2)

        # Search for "Conferencias"
        response = client.get("/salas/search/nombre?nombre=Conferencias")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["nombre"] == "Sala de Conferencias"

    def test_search_by_nombre_partial_match(self):
        """Test search with partial match."""
        # Create salas
        sala_data1 = {
            "nombre": "Sala de Conferencias A",
            "ubicacion": "Piso 1",
            "capacidad": 20,
        }
        sala_data2 = {
            "nombre": "Sala de Conferencias B",
            "ubicacion": "Piso 2",
            "capacidad": 15,
        }
        client.post("/salas", json=sala_data1)
        client.post("/salas", json=sala_data2)

        # Search for "Conferencias"
        response = client.get("/salas/search/nombre?nombre=Conferencias")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_search_by_nombre_no_results(self):
        """Test search with no results."""
        response = client.get("/salas/search/nombre?nombre=NoExiste")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_search_by_nombre_empty_query(self):
        """Test search with empty query."""
        response = client.get("/salas/search/nombre?nombre=")
        assert response.status_code == 422


class TestSearchByCapacidad:
    """Test searching salas by capacity."""

    def test_search_by_capacidad_found(self):
        """Test successful search by capacity."""
        # Create salas
        sala_data1 = {"nombre": "Sala A", "ubicacion": "Piso 1", "capacidad": 50}
        sala_data2 = {"nombre": "Sala B", "ubicacion": "Piso 2", "capacidad": 20}
        sala_data3 = {"nombre": "Sala C", "ubicacion": "Piso 3", "capacidad": 10}
        client.post("/salas", json=sala_data1)
        client.post("/salas", json=sala_data2)
        client.post("/salas", json=sala_data3)

        # Search for capacity >= 20
        response = client.get("/salas/search/capacidad?capacidad_minima=20")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_search_by_capacidad_no_results(self):
        """Test search with no results."""
        # Create a sala
        sala_data = {"nombre": "Sala A", "ubicacion": "Piso 1", "capacidad": 10}
        client.post("/salas", json=sala_data)

        # Search for capacity >= 50
        response = client.get("/salas/search/capacidad?capacidad_minima=50")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_search_by_capacidad_invalid_value(self):
        """Test search with invalid capacity value."""
        response = client.get("/salas/search/capacidad?capacidad_minima=0")
        assert response.status_code == 400

    def test_search_by_capacidad_negative_value(self):
        """Test search with negative capacity value."""
        response = client.get("/salas/search/capacidad?capacidad_minima=-5")
        assert response.status_code == 400


class TestIntegration:
    """Integration tests combining multiple operations."""

    def test_full_crud_workflow(self):
        """Test complete CRUD workflow."""
        # Create
        sala_data = {
            "nombre": "Integration Test Sala",
            "ubicacion": "Piso Test",
            "capacidad": 25,
            "equipamiento": ["TV", "Whiteboard"],
        }
        create_response = client.post("/salas", json=sala_data)
        assert create_response.status_code == 201
        sala = create_response.json()
        sala_id = sala["id"]

        # Read
        get_response = client.get(f"/salas/{sala_id}")
        assert get_response.status_code == 200
        assert get_response.json()["nombre"] == sala_data["nombre"]

        # Update
        update_data = {
            "capacidad": 30,
            "equipamiento": ["TV", "Whiteboard", "Videoconferencia"],
        }
        update_response = client.put(f"/salas/{sala_id}", json=update_data)
        assert update_response.status_code == 200
        assert update_response.json()["capacidad"] == 30

        # Delete
        delete_response = client.delete(f"/salas/{sala_id}")
        assert delete_response.status_code == 200

        # Verify deleted
        final_response = client.get(f"/salas/{sala_id}")
        assert final_response.status_code == 404

    def test_multiple_operations_pagination(self):
        """Test multiple operations with pagination."""
        # Create 25 salas
        for i in range(25):
            sala_data = {
                "nombre": f"Sala Numero {i}",
                "ubicacion": f"Piso {i % 5}",
                "capacidad": 10 + (i % 20),
            }
            client.post("/salas", json=sala_data)

        # Test pagination
        page1 = client.get("/salas?skip=0&limit=10")
        assert len(page1.json()["items"]) == 10

        page2 = client.get("/salas?skip=10&limit=10")
        assert len(page2.json()["items"]) == 10

        page3 = client.get("/salas?skip=20&limit=10")
        assert len(page3.json()["items"]) == 5

        # Total should be 25
        assert page1.json()["total"] == 25
