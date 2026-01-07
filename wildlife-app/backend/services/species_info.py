"""Species information database and service"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class SpeciesInfo:
    """Detailed information about a wildlife species"""
    
    def __init__(
        self,
        common_name: str,
        scientific_name: str,
        description: str,
        habitat: str,
        behavior: str,
        diet: str,
        size: str,
        weight: str,
        conservation_status: str,
        activity_pattern: str,
        geographic_range: str,
        interesting_facts: List[str],
        image_url: Optional[str] = None
    ):
        self.common_name = common_name
        self.scientific_name = scientific_name
        self.description = description
        self.habitat = habitat
        self.behavior = behavior
        self.diet = diet
        self.size = size
        self.weight = weight
        self.conservation_status = conservation_status
        self.activity_pattern = activity_pattern
        self.geographic_range = geographic_range
        self.interesting_facts = interesting_facts
        self.image_url = image_url
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "common_name": self.common_name,
            "scientific_name": self.scientific_name,
            "description": self.description,
            "habitat": self.habitat,
            "behavior": self.behavior,
            "diet": self.diet,
            "size": self.size,
            "weight": self.weight,
            "conservation_status": self.conservation_status,
            "activity_pattern": self.activity_pattern,
            "geographic_range": self.geographic_range,
            "interesting_facts": self.interesting_facts,
            "image_url": self.image_url
        }


class SpeciesInfoService:
    """Service for retrieving species information"""
    
    def __init__(self):
        self.species_database = self._initialize_species_database()
    
    def _initialize_species_database(self) -> Dict[str, SpeciesInfo]:
        """Initialize the species information database"""
        species = {}
        
        # White-tailed Deer
        species["deer"] = SpeciesInfo(
            common_name="White-tailed Deer",
            scientific_name="Odocoileus virginianus",
            description="The white-tailed deer is a medium-sized deer native to North America, Central America, and South America. It is named for the white underside of its tail, which it raises as a warning signal when alarmed.",
            habitat="Forests, woodlands, grasslands, and suburban areas. Prefers areas with a mix of open fields and dense cover.",
            behavior="Most active during dawn and dusk (crepuscular). Solitary or in small groups. Males (bucks) are territorial during breeding season. Excellent swimmers and can run up to 30 mph.",
            diet="Herbivorous - feeds on leaves, twigs, fruits, nuts, acorns, and agricultural crops. Diet varies by season.",
            size="Length: 4-7 feet (1.2-2.1 m), Height: 2-4 feet (0.6-1.2 m) at shoulder",
            weight="Males: 150-300 lbs (68-136 kg), Females: 90-200 lbs (41-91 kg)",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Crepuscular (dawn and dusk), with some nocturnal activity",
            geographic_range="North America from southern Canada to northern South America",
            interesting_facts=[
                "Can jump up to 10 feet high and 30 feet long",
                "Antlers are shed and regrown annually",
                "Have excellent hearing and sense of smell",
                "Can live up to 20 years in the wild",
                "White tail is raised as a warning signal to other deer"
            ]
        )
        
        # Raccoon
        species["raccoon"] = SpeciesInfo(
            common_name="Raccoon",
            scientific_name="Procyon lotor",
            description="The raccoon is a medium-sized mammal native to North America. Known for its distinctive black 'mask' around the eyes and ringed tail. Highly adaptable and intelligent.",
            habitat="Forests, wetlands, urban areas, and suburban neighborhoods. Prefers areas near water with trees for denning.",
            behavior="Nocturnal and highly intelligent. Excellent climbers and swimmers. Omnivorous and opportunistic feeders. Known for 'washing' food in water.",
            diet="Omnivorous - eats fruits, nuts, insects, small animals, eggs, fish, and human garbage. Very adaptable diet.",
            size="Length: 24-38 inches (60-95 cm), Height: 9-12 inches (23-30 cm) at shoulder",
            weight="8-20 lbs (3.6-9 kg), with males typically larger",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Primarily nocturnal, with some crepuscular activity",
            geographic_range="Native to North America, introduced to Europe and Asia",
            interesting_facts=[
                "Have highly sensitive front paws with 5 times more nerve endings than human hands",
                "Can remember solutions to tasks for up to 3 years",
                "Excellent problem solvers - can open complex latches and containers",
                "Can run up to 15 mph and climb trees headfirst",
                "The 'washing' behavior is actually food manipulation, not cleaning"
            ]
        )
        
        # Squirrel
        species["squirrel"] = SpeciesInfo(
            common_name="Eastern Gray Squirrel",
            scientific_name="Sciurus carolinensis",
            description="The eastern gray squirrel is a tree-dwelling rodent native to eastern North America. Known for its bushy tail and acrobatic abilities.",
            habitat="Deciduous and mixed forests, urban parks, and suburban areas with mature trees. Prefers hardwood forests with nut-producing trees.",
            behavior="Diurnal and highly active. Excellent climbers and jumpers. Caches food for winter. Very territorial and vocal.",
            diet="Omnivorous - primarily nuts, seeds, fruits, buds, flowers, and occasionally insects, eggs, and small birds",
            size="Length: 9-12 inches (23-30 cm) body, Tail: 7-10 inches (18-25 cm)",
            weight="14-21 oz (400-600 g)",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Diurnal (active during day), most active in morning and late afternoon",
            geographic_range="Eastern United States and Canada, introduced to western US, UK, and other regions",
            interesting_facts=[
                "Can jump up to 20 feet horizontally",
                "Can fall from 100 feet without injury due to flexible joints",
                "Have excellent spatial memory - can remember thousands of cache locations",
                "Can run up to 20 mph",
                "Tail helps with balance and communication"
            ]
        )
        
        # Bird (general)
        species["bird"] = SpeciesInfo(
            common_name="Wild Birds",
            scientific_name="Various species",
            description="A diverse group of warm-blooded vertebrates characterized by feathers, beaks, and the ability to fly (most species). Includes songbirds, raptors, waterfowl, and many other types.",
            habitat="Varies by species - forests, grasslands, wetlands, urban areas, and many other habitats worldwide",
            behavior="Highly diverse behaviors. Most are diurnal, some are nocturnal. Many migrate seasonally. Social structures vary from solitary to large flocks.",
            diet="Varies widely - seeds, fruits, insects, fish, small mammals, nectar, and more depending on species",
            size="Varies dramatically - from 2 inches (hummingbirds) to over 9 feet (ostriches)",
            weight="Varies from less than 1 oz to over 300 lbs",
            conservation_status="Varies by species - many are declining due to habitat loss",
            activity_pattern="Most are diurnal, some are nocturnal (owls, nightjars)",
            geographic_range="Worldwide - found on every continent including Antarctica",
            interesting_facts=[
                "There are over 10,000 bird species worldwide",
                "Birds are the only living descendants of dinosaurs",
                "Some birds can fly at speeds over 200 mph",
                "Many birds migrate thousands of miles annually",
                "Birds have excellent color vision - can see UV light"
            ]
        )
        
        # Cat (domestic/wild)
        species["cat"] = SpeciesInfo(
            common_name="Domestic Cat / Feral Cat",
            scientific_name="Felis catus",
            description="The domestic cat is a small carnivorous mammal. Feral and outdoor cats are common in suburban and rural areas. Highly adaptable predators.",
            habitat="Highly adaptable - can live in urban, suburban, rural, and wild areas. Prefers areas with cover and food sources.",
            behavior="Crepuscular and nocturnal. Solitary hunters but can form colonies. Excellent climbers and jumpers. Territorial.",
            diet="Carnivorous - primarily small mammals, birds, reptiles, and insects. Will also eat human-provided food.",
            size="Length: 18-30 inches (46-76 cm), Height: 9-10 inches (23-25 cm) at shoulder",
            weight="8-15 lbs (3.6-6.8 kg) for domestic cats, feral cats often smaller",
            conservation_status="Domesticated - not applicable",
            activity_pattern="Crepuscular (dawn and dusk) with significant nocturnal activity",
            geographic_range="Worldwide - found wherever humans have settled",
            interesting_facts=[
                "Can jump up to 6 times their body length",
                "Have excellent night vision - 6 times better than humans",
                "Can run up to 30 mph in short bursts",
                "Have retractable claws for climbing and hunting",
                "Feral cats can have significant impact on local wildlife populations"
            ]
        )
        
        # Dog (domestic/wild)
        species["dog"] = SpeciesInfo(
            common_name="Domestic Dog / Feral Dog",
            scientific_name="Canis lupus familiaris",
            description="The domestic dog is a domesticated descendant of the wolf. Feral and stray dogs can be found in many areas. Highly social and intelligent.",
            habitat="Highly adaptable - can live in urban, suburban, and rural areas. Prefers areas with food sources and shelter.",
            behavior="Social animals, often in packs. Diurnal and crepuscular. Excellent sense of smell and hearing. Territorial.",
            diet="Omnivorous - can eat meat, grains, fruits, and human food. Opportunistic feeders.",
            size="Varies dramatically by breed - from 6 inches to over 3 feet tall",
            weight="Varies from 4 lbs to over 200 lbs depending on breed",
            conservation_status="Domesticated - not applicable",
            activity_pattern="Primarily diurnal with some crepuscular activity",
            geographic_range="Worldwide - found wherever humans have settled",
            interesting_facts=[
                "Have 300 million olfactory receptors (humans have 6 million)",
                "Can hear frequencies up to 65,000 Hz (humans: 20,000 Hz)",
                "Can run up to 45 mph (greyhounds)",
                "Highly social - descended from pack animals",
                "Feral dogs can form packs and hunt wildlife"
            ]
        )
        
        # Human
        species["human"] = SpeciesInfo(
            common_name="Human",
            scientific_name="Homo sapiens",
            description="Humans are the most widespread and dominant species on Earth. In wildlife monitoring contexts, human detections typically indicate human activity in wildlife areas.",
            habitat="Found in virtually all terrestrial habitats worldwide, from arctic tundra to tropical rainforests",
            behavior="Highly social, diurnal, tool-using, and adaptable. Can significantly impact local wildlife through habitat modification.",
            diet="Omnivorous - extremely varied diet including plants, animals, and processed foods",
            size="Average height: 5-6 feet (1.5-1.8 m), varies by population",
            weight="Average: 120-200 lbs (54-91 kg), varies significantly",
            conservation_status="Least Concern - population over 8 billion",
            activity_pattern="Primarily diurnal, with some nocturnal activity",
            geographic_range="Worldwide - found on all continents",
            interesting_facts=[
                "Humans are the most intelligent species on Earth",
                "Can significantly modify and impact wildlife habitats",
                "Have the largest geographic range of any mammal",
                "Can adapt to extreme environments from deserts to arctic",
                "Human activity is a major factor in wildlife monitoring"
            ]
        )
        
        # Vehicle
        species["vehicle"] = SpeciesInfo(
            common_name="Vehicle",
            scientific_name="N/A",
            description="Motor vehicles including cars, trucks, motorcycles, and other motorized transportation. Detections typically indicate human activity or traffic in monitored areas.",
            habitat="Roads, parking areas, and any area accessible by vehicles",
            behavior="Operated by humans, follows roads and paths. Can disturb wildlife and create noise pollution.",
            diet="N/A - requires fuel (gasoline, diesel, electric)",
            size="Varies - from motorcycles (6 feet) to large trucks (40+ feet)",
            weight="Varies from 300 lbs (motorcycles) to 80,000+ lbs (large trucks)",
            conservation_status="N/A",
            activity_pattern="Primarily diurnal, with some nocturnal activity",
            geographic_range="Worldwide - wherever roads and infrastructure exist",
            interesting_facts=[
                "Vehicles are a major cause of wildlife mortality",
                "Can create barriers to wildlife movement",
                "Noise and light pollution can affect wildlife behavior",
                "Roads fragment wildlife habitats",
                "Vehicle detection helps monitor human activity in wildlife areas"
            ]
        )
        
        # Add more species as needed
        species["fox"] = SpeciesInfo(
            common_name="Red Fox",
            scientific_name="Vulpes vulpes",
            description="The red fox is the largest of the true foxes and one of the most widely distributed members of the order Carnivora. Known for its reddish fur and bushy tail.",
            habitat="Forests, grasslands, mountains, deserts, and urban areas. Highly adaptable to various environments.",
            behavior="Nocturnal and crepuscular. Solitary hunters. Excellent hearing - can hear rodents underground. Very intelligent and adaptable.",
            diet="Omnivorous - small mammals, birds, insects, fruits, berries, and human garbage. Opportunistic feeders.",
            size="Length: 18-35 inches (46-90 cm), Height: 14-16 inches (35-40 cm) at shoulder",
            weight="6-15 lbs (2.7-6.8 kg)",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Primarily nocturnal and crepuscular",
            geographic_range="Northern Hemisphere - North America, Europe, Asia, and introduced to Australia",
            interesting_facts=[
                "Can jump up to 6 feet high",
                "Have excellent hearing - can hear a mouse squeak from 100 feet away",
                "Can run up to 30 mph",
                "Have whiskers on their legs to help navigate in the dark",
                "Can adapt to urban environments very well"
            ]
        )
        
        species["coyote"] = SpeciesInfo(
            common_name="Coyote",
            scientific_name="Canis latrans",
            description="The coyote is a medium-sized canine native to North America. Highly adaptable and intelligent, known for its distinctive howl.",
            habitat="Prairies, forests, deserts, and increasingly urban and suburban areas. Very adaptable.",
            behavior="Crepuscular and nocturnal. Social animals that form packs. Excellent hunters and scavengers. Very vocal.",
            diet="Omnivorous - small mammals, birds, reptiles, fruits, berries, and human garbage. Opportunistic feeders.",
            size="Length: 32-37 inches (81-94 cm), Height: 20-22 inches (51-56 cm) at shoulder",
            weight="20-50 lbs (9-23 kg)",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Primarily crepuscular and nocturnal",
            geographic_range="North America - from Alaska to Central America",
            interesting_facts=[
                "Can run up to 40 mph",
                "Can jump up to 13 feet",
                "Have excellent sense of smell - 100 times better than humans",
                "Can adapt to urban environments",
                "Known for their distinctive howling and yipping calls"
            ]
        )
        
        species["opossum"] = SpeciesInfo(
            common_name="Virginia Opossum",
            scientific_name="Didelphis virginiana",
            description="The Virginia opossum is North America's only marsupial. Known for playing dead when threatened and its prehensile tail.",
            habitat="Forests, woodlands, and urban areas. Prefers areas near water with trees.",
            behavior="Nocturnal and solitary. Slow-moving but good climbers. Known for 'playing possum' when threatened.",
            diet="Omnivorous - fruits, insects, small animals, eggs, carrion, and human garbage. Very opportunistic.",
            size="Length: 13-37 inches (33-94 cm), Height: 8-10 inches (20-25 cm) at shoulder",
            weight="4-14 lbs (1.8-6.4 kg)",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Primarily nocturnal",
            geographic_range="Eastern and Central United States, introduced to West Coast",
            interesting_facts=[
                "North America's only marsupial",
                "Have 50 teeth - more than any other North American mammal",
                "Immune to most snake venoms",
                "Can hang by their prehensile tail",
                "Playing dead is an involuntary response that can last up to 4 hours"
            ]
        )
        
        species["rabbit"] = SpeciesInfo(
            common_name="Eastern Cottontail Rabbit",
            scientific_name="Sylvilagus floridanus",
            description="The eastern cottontail is a common rabbit species in North America. Known for its white cotton-like tail and excellent jumping ability.",
            habitat="Grasslands, fields, brushy areas, and suburban yards. Prefers areas with dense cover nearby.",
            behavior="Crepuscular and nocturnal. Solitary except during breeding. Excellent jumpers and runners. Freeze when threatened.",
            diet="Herbivorous - grasses, clover, dandelions, and other plants. Also eats bark and twigs in winter.",
            size="Length: 14-19 inches (36-48 cm), Height: 5-7 inches (13-18 cm) at shoulder",
            weight="2-4 lbs (0.9-1.8 kg)",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Primarily crepuscular and nocturnal",
            geographic_range="Eastern and Central United States, parts of Canada and Mexico",
            interesting_facts=[
                "Can jump up to 10 feet in a single bound",
                "Can run up to 18 mph in zigzag patterns",
                "Have 360-degree vision",
                "Can have up to 7 litters per year",
                "Freeze when threatened to avoid detection"
            ]
        )
        
        species["skunk"] = SpeciesInfo(
            common_name="Striped Skunk",
            scientific_name="Mephitis mephitis",
            description="The striped skunk is known for its distinctive black and white stripes and powerful defensive spray. Common in North America.",
            habitat="Forests, grasslands, and suburban areas. Prefers areas with cover and food sources.",
            behavior="Nocturnal and solitary. Slow-moving but good diggers. Famous for defensive spray that can reach 10 feet.",
            diet="Omnivorous - insects, small mammals, eggs, fruits, berries, and human garbage.",
            size="Length: 20-30 inches (51-76 cm), Height: 6-8 inches (15-20 cm) at shoulder",
            weight="4-10 lbs (1.8-4.5 kg)",
            conservation_status="Least Concern (IUCN)",
            activity_pattern="Primarily nocturnal",
            geographic_range="North America - from Canada to northern Mexico",
            interesting_facts=[
                "Can spray up to 10 feet with 95% accuracy",
                "Spray can cause temporary blindness",
                "Have poor eyesight but excellent sense of smell",
                "Can carry rabies but are not aggressive",
                "Stripes serve as a warning to predators"
            ]
        )
        
        return species
    
    def get_species_info(self, species_name: str) -> Optional[Dict[str, Any]]:
        """Get species information by name (case-insensitive)"""
        if not species_name:
            return None
        
        species_lower = species_name.lower().strip()
        
        # Try direct match
        if species_lower in self.species_database:
            return self.species_database[species_lower].to_dict()
        
        # Try partial matches
        for key, info in self.species_database.items():
            if key in species_lower or species_lower in key:
                return info.to_dict()
        
        # Try common name matches
        for key, info in self.species_database.items():
            if info.common_name.lower() in species_lower or species_lower in info.common_name.lower():
                return info.to_dict()
        
        # Try scientific name matches
        for key, info in self.species_database.items():
            if info.scientific_name.lower() in species_lower or species_lower in info.scientific_name.lower():
                return info.to_dict()
        
        return None
    
    def get_all_species(self) -> List[Dict[str, Any]]:
        """Get information for all species"""
        return [info.to_dict() for info in self.species_database.values()]
    
    def search_species(self, query: str) -> List[Dict[str, Any]]:
        """Search species by name, scientific name, or description"""
        if not query:
            return []
        
        query_lower = query.lower()
        results = []
        
        for key, info in self.species_database.items():
            # Check common name
            if query_lower in info.common_name.lower():
                results.append(info.to_dict())
                continue
            
            # Check scientific name
            if query_lower in info.scientific_name.lower():
                results.append(info.to_dict())
                continue
            
            # Check description
            if query_lower in info.description.lower():
                results.append(info.to_dict())
                continue
        
        return results


# Global service instance
species_info_service = SpeciesInfoService()

