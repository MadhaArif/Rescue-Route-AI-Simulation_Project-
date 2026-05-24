from rescueroute.ml_model import ArrivalTimePredictor, generate_training_data
from rescueroute.config import DATA_DIR, MODEL_PATH


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dataset = generate_training_data(rows=7000, seed=123)
    dataset_path = DATA_DIR / "synthetic_arrival_time_dataset.csv"
    dataset.to_csv(dataset_path, index=False)

    predictor = ArrivalTimePredictor(model_path=MODEL_PATH, auto_train=False)
    metrics = predictor.train_and_save(rows=7000, seed=123)

    print("Training complete")
    print(f"Dataset saved to: {dataset_path}")
    print(f"Model saved to: {MODEL_PATH}")
    print(f"MAE: {metrics['mae_minutes']:.2f} minutes")
    print(f"R²: {metrics['r2']:.3f}")


if __name__ == "__main__":
    main()
