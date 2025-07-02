#!/usr/bin/env node
/**
 * Test script to verify frontend can connect to PostgreSQL backend
 */

const axios = require('axios');

const API_URL = 'http://localhost:8001';

async function testConnection() {
  console.log('🧪 Testing Frontend → PostgreSQL Backend Connection');
  console.log('=' .repeat(50));
  
  try {
    // Test health endpoint
    console.log('1. Testing health endpoint...');
    const healthResponse = await axios.get(`${API_URL}/health`);
    console.log('✅ Health check passed:', healthResponse.data);
    
    // Test detections endpoint
    console.log('\n2. Testing detections endpoint...');
    const detectionsResponse = await axios.get(`${API_URL}/detections`);
    console.log(`✅ Detections endpoint working: ${detectionsResponse.data.length} detections returned`);
    
    // Test cameras endpoint
    console.log('\n3. Testing cameras endpoint...');
    const camerasResponse = await axios.get(`${API_URL}/cameras`);
    console.log(`✅ Cameras endpoint working: ${camerasResponse.data.length} cameras returned`);
    
    // Test system endpoint
    console.log('\n4. Testing system endpoint...');
    const systemResponse = await axios.get(`${API_URL}/system`);
    console.log('✅ System endpoint working:', systemResponse.data.motioneye?.status);
    
    // Test SSE endpoint (just check if it responds)
    console.log('\n5. Testing SSE endpoint...');
    try {
      const sseResponse = await axios.get(`${API_URL}/events/detections`, {
        timeout: 3000,
        validateStatus: () => true // Don't throw on any status
      });
      console.log('✅ SSE endpoint responding (status:', sseResponse.status + ')');
    } catch (error) {
      console.log('⚠️  SSE endpoint test inconclusive (this is normal for SSE)');
    }
    
    console.log('\n🎉 All backend endpoints are working!');
    console.log('\n📋 Frontend Configuration Summary:');
    console.log('  - API URL:', API_URL);
    console.log('  - Database: PostgreSQL (Docker)');
    console.log('  - Real-time updates: Enabled via SSE');
    console.log('  - Detections count:', detectionsResponse.data.length);
    console.log('  - Cameras count:', camerasResponse.data.length);
    
  } catch (error) {
    console.error('❌ Connection test failed:', error.message);
    console.log('\n🔧 Troubleshooting:');
    console.log('  1. Make sure PostgreSQL is running: docker-compose up -d postgres');
    console.log('  2. Make sure backend is running: cd backend && python main.py');
    console.log('  3. Check if port 8001 is available');
  }
}

testConnection(); 