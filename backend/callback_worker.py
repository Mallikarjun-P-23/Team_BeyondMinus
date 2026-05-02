"""
Callback Worker - Background process for handling automatic callbacks
Runs continuously to process due callback requests
"""
import asyncio
import asyncpg
import os
import sys
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.callback_service import CallbackService
from app.services.elevenlabs_service import ElevenLabsService
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CallbackWorker:
    """Background worker that processes callback requests"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_pool = None
        self.callback_service = None
        self.running = False
    
    async def initialize(self):
        """Initialize database connection and services"""
        logger.info("Initializing Callback Worker...")
        
        # Create database pool
        self.db_pool = await asyncpg.create_pool(
            self.settings.DATABASE_URL,
            min_size=2,
            max_size=5
        )
        
        # Initialize services
        elevenlabs_service = ElevenLabsService()
        self.callback_service = CallbackService(
            db_pool=self.db_pool,
            elevenlabs_service=elevenlabs_service
        )
        
        logger.info("Callback Worker initialized successfully")
    
    async def run(self):
        """Main worker loop"""
        self.running = True
        logger.info("Starting Callback Worker main loop...")
        
        while self.running:
            try:
                # Process due callbacks
                await self.callback_service.process_due_callbacks()
                
                # Sleep for 5 seconds before next check
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in callback worker loop: {str(e)}", exc_info=True)
                await asyncio.sleep(10)  # Wait longer on error
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down Callback Worker...")
        self.running = False
        
        if self.db_pool:
            await self.db_pool.close()
        
        logger.info("Callback Worker shut down complete")


async def main():
    """Entry point for callback worker"""
    worker = CallbackWorker()
    
    try:
        await worker.initialize()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error in callback worker: {str(e)}", exc_info=True)
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
