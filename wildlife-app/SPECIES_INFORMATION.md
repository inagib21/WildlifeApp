# Species Information System

The Wildlife Detection System now includes comprehensive species information for detected animals, providing detailed educational content about each species.

## Features

### 1. **Comprehensive Species Database** 📚
Detailed information for common wildlife species including:

- **White-tailed Deer** (Odocoileus virginianus)
- **Raccoon** (Procyon lotor)
- **Eastern Gray Squirrel** (Sciurus carolinensis)
- **Wild Birds** (Various species)
- **Domestic/Feral Cat** (Felis catus)
- **Domestic/Feral Dog** (Canis lupus familiaris)
- **Red Fox** (Vulpes vulpes)
- **Coyote** (Canis latrans)
- **Virginia Opossum** (Didelphis virginiana)
- **Eastern Cottontail Rabbit** (Sylvilagus floridanus)
- **Striped Skunk** (Mephitis mephitis)
- **Human** (Homo sapiens)
- **Vehicle** (for monitoring human activity)

### 2. **Detailed Information for Each Species** 🦌

Each species entry includes:

- **Common Name**: Standard common name
- **Scientific Name**: Binomial nomenclature
- **Description**: Detailed physical and behavioral description
- **Habitat**: Preferred habitats and environments
- **Behavior**: Activity patterns, social behavior, and notable behaviors
- **Diet**: What the species eats
- **Size**: Length and height measurements
- **Weight**: Typical weight ranges
- **Conservation Status**: IUCN conservation status
- **Activity Pattern**: When the species is most active (diurnal, nocturnal, crepuscular)
- **Geographic Range**: Where the species is found
- **Interesting Facts**: 5+ fascinating facts about the species

### 3. **API Endpoints** 🔌

#### Get All Species
```
GET /api/species
```
Returns information for all species in the database.

**Response:**
```json
{
  "count": 12,
  "species": [
    {
      "common_name": "White-tailed Deer",
      "scientific_name": "Odocoileus virginianus",
      "description": "...",
      "habitat": "...",
      ...
    }
  ]
}
```

#### Get Species by Name
```
GET /api/species/{species_name}
```
Returns detailed information for a specific species. Supports:
- Common names (e.g., "deer", "raccoon")
- Scientific names (e.g., "Odocoileus virginianus")
- Partial matches (e.g., "white-tailed" matches "White-tailed Deer")

**Example:**
```
GET /api/species/deer
GET /api/species/raccoon
GET /api/species/Odocoileus%20virginianus
```

#### Search Species
```
GET /api/species/search?q={query}
```
Searches species by name, scientific name, or description.

**Example:**
```
GET /api/species/search?q=nocturnal
GET /api/species/search?q=forest
```

### 4. **Enhanced Detection Responses** 📊

Detection responses now automatically include species information:

```json
{
  "id": 12345,
  "camera_id": 1,
  "timestamp": "2025-12-16T19:30:00Z",
  "species": "Deer",
  "confidence": 0.85,
  "species_info": {
    "common_name": "White-tailed Deer",
    "scientific_name": "Odocoileus virginianus",
    "description": "The white-tailed deer is a medium-sized deer...",
    "habitat": "Forests, woodlands, grasslands...",
    "behavior": "Most active during dawn and dusk...",
    "diet": "Herbivorous - feeds on leaves, twigs...",
    "size": "Length: 4-7 feet (1.2-2.1 m)...",
    "weight": "Males: 150-300 lbs (68-136 kg)...",
    "conservation_status": "Least Concern (IUCN)",
    "activity_pattern": "Crepuscular (dawn and dusk)...",
    "geographic_range": "North America from southern Canada...",
    "interesting_facts": [
      "Can jump up to 10 feet high and 30 feet long",
      "Antlers are shed and regrown annually",
      ...
    ]
  }
}
```

## Usage Examples

### Frontend Integration

```typescript
// Get species information for a detection
const detection = await getDetection(detectionId);
if (detection.species_info) {
  console.log(`Species: ${detection.species_info.common_name}`);
  console.log(`Scientific Name: ${detection.species_info.scientific_name}`);
  console.log(`Habitat: ${detection.species_info.habitat}`);
  console.log(`Interesting Facts:`, detection.species_info.interesting_facts);
}

// Search for species
const results = await fetch('/api/species/search?q=nocturnal');
const species = await results.json();
```

### Backend Usage

```python
from services.species_info import species_info_service

# Get species information
info = species_info_service.get_species_info("deer")
if info:
    print(f"Common Name: {info['common_name']}")
    print(f"Scientific Name: {info['scientific_name']}")
    print(f"Description: {info['description']}")

# Search species
results = species_info_service.search_species("nocturnal")
for species in results:
    print(f"Found: {species['common_name']}")
```

## Benefits

1. **Educational Value**: Users learn about detected wildlife
2. **Better Context**: Understanding species behavior helps interpret detections
3. **Conservation Awareness**: Conservation status information raises awareness
4. **Rich Metadata**: Comprehensive information enhances detection records
5. **Searchable**: Easy to find information about specific species or behaviors

## Adding New Species

To add a new species, edit `wildlife-app/backend/services/species_info.py`:

```python
species["new_species"] = SpeciesInfo(
    common_name="New Species Name",
    scientific_name="Scientific name",
    description="Description...",
    habitat="Habitat information...",
    behavior="Behavior information...",
    diet="Diet information...",
    size="Size information...",
    weight="Weight information...",
    conservation_status="Conservation status...",
    activity_pattern="Activity pattern...",
    geographic_range="Geographic range...",
    interesting_facts=[
        "Fact 1",
        "Fact 2",
        ...
    ]
)
```

## Future Enhancements

Potential improvements:
- Species images/photos
- Seasonal behavior patterns
- Migration information
- Breeding season details
- Predator-prey relationships
- Conservation efforts
- Local distribution maps
- Audio recordings (calls, sounds)

