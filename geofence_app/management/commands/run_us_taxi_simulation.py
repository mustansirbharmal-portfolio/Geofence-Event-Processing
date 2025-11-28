"""
Django management command to run the US taxi simulation.
"""

import time
import signal
import sys
from django.core.management.base import BaseCommand
from us_taxi_simulation import us_taxi_simulation


class Command(BaseCommand):
    help = 'Run the US multi-state taxi simulation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--duration',
            type=int,
            default=0,
            help='Duration to run simulation in seconds (0 = run indefinitely)'
        )
        parser.add_argument(
            '--status-interval',
            type=int,
            default=30,
            help='Interval between status updates in seconds'
        )

    def handle(self, *args, **options):
        duration = options['duration']
        status_interval = options['status_interval']
        
        self.stdout.write(
            self.style.SUCCESS('Starting US Multi-State Taxi Simulation...')
        )
        
        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            self.stdout.write(
                self.style.WARNING('\nReceived interrupt signal. Stopping simulation...')
            )
            us_taxi_simulation.stop_simulation()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Start the simulation
            us_taxi_simulation.start_simulation()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Simulation started with {len(us_taxi_simulation.taxis)} taxis'
                )
            )
            
            # Print initial status
            self._print_status()
            
            # Run for specified duration or indefinitely
            start_time = time.time()
            last_status_time = start_time
            
            while True:
                current_time = time.time()
                
                # Check if duration limit reached
                if duration > 0 and (current_time - start_time) >= duration:
                    self.stdout.write(
                        self.style.SUCCESS(f'Simulation completed after {duration} seconds')
                    )
                    break
                
                # Print status update
                if (current_time - last_status_time) >= status_interval:
                    self._print_status()
                    last_status_time = current_time
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('Simulation interrupted by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Simulation error: {e}')
            )
        finally:
            us_taxi_simulation.stop_simulation()
            self.stdout.write(
                self.style.SUCCESS('Simulation stopped')
            )
    
    def _print_status(self):
        """Print current status of all taxis."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS('🚖 TAXI STATUS UPDATE')
        )
        self.stdout.write('='*60)
        
        for taxi_id, status in us_taxi_simulation.get_all_taxis_status().items():
            current_route = status.get('current_route', {})
            pickup_state = current_route.get('pickup', {}).get('state', 'Unknown')
            dropoff_state = current_route.get('dropoff', {}).get('state', 'Unknown')
            progress = status.get('route_progress', 0) * 100
            current_zone = status.get('current_zone', 'Unknown')
            
            self.stdout.write(
                f"🚕 {taxi_id.upper():<8} | "
                f"Zone: {current_zone:<15} | "
                f"Route: {pickup_state} → {dropoff_state:<15} | "
                f"Progress: {progress:5.1f}%"
            )
        
        self.stdout.write('='*60 + '\n')
